"""Carrier lifecycle bridge to the scheduler-owned transport admission policy."""

from tigrcorn_protocols.scheduler.admission import AdmissionDenied


class HTTP3AdmissionMixin:
    def _admission(self):
        return getattr(self.scheduler, "admission", None)

    def _admit_h3_connection(self, session):
        admission = self._admission()
        if admission is None or session.admission_connection is not None:
            return True
        session.admission_source = session.addr
        try:
            session.admission_connection = admission.acquire(
                "connection",
                source=session.admission_source,
                connection_id=self._connection_id_for_session(session),
            )
        except AdmissionDenied:
            return False
        return True

    def _reap_admission_streams(self, session):
        for stream_id, lease in list(session.admission_streams.items()):
            state = session.quic.streams._streams.get(stream_id)
            if state is not None and state.closed:
                lease.release()
                session.admission_streams.pop(stream_id, None)
                session_lease = session.admission_sessions.pop(str(stream_id), None)
                if session_lease is not None:
                    session_lease.release()

    def _admit_h3_stream(self, session, stream_id, data=b"", *, client_initiated=True):
        admission = self._admission()
        if admission is None:
            return
        self._reap_admission_streams(session)
        if (
            stream_id in session.admission_streams
            or stream_id in session.admission_controls
        ):
            return
        state = session.quic.streams._streams.get(stream_id)
        if state is not None and state.closed:
            return
        if (
            stream_id % 4 == 2
            and not data
            and len(session.admission_pending_controls | session.admission_controls) < 3
        ):
            session.admission_pending_controls.add(stream_id)
            return
        session.admission_pending_controls.discard(stream_id)
        # H3 critical peer streams have a separate fixed reservation. H3 validates
        # duplicate control/QPACK types; application unidirectional streams do not
        # consume these reservations merely because they are unidirectional.
        if (
            stream_id % 4 == 2
            and data
            and data[0] in (0, 2, 3)
            and len(session.admission_controls) < 3
        ):
            session.admission_controls.add(stream_id)
            return
        session.admission_streams[stream_id] = admission.acquire(
            "stream",
            source=session.admission_source or session.addr,
            connection_id=self._connection_id_for_session(session),
            client_initiated=client_initiated,
        )

    def _admit_h3_protocol_session(self, session, key):
        admission = self._admission()
        key = str(key)
        if admission is not None and key not in session.admission_sessions:
            session.admission_sessions[key] = admission.acquire(
                "session",
                source=session.admission_source or session.addr,
                connection_id=self._connection_id_for_session(session),
            )

    def _release_h3_admission(self, session):
        admission = self._admission()
        if admission is not None:
            admission.release_connection(self._connection_id_for_session(session))
        session.admission_streams.clear()
        session.admission_sessions.clear()

    def _refuse_h3_stream(self, session, stream_id):
        # Peer unidirectional streams have no local send direction to reset.
        frames = [session.quic.stop_sending(stream_id, 0x107)]
        if stream_id % 4 in (0, 1):
            frames.append(session.quic.reset_stream(stream_id, 0x107))
        lease = session.admission_streams.pop(stream_id, None)
        if lease is not None:
            lease.release()
        return frames
