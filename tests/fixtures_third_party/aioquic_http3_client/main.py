from __future__ import annotations

import json
import os
import sys

from .client_core import *
from .exchanges import _perform_connect_relay_exchange, _perform_single_exchange

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        try:
            import aioquic  # type: ignore
        except ModuleNotFoundError:
            print("aioquic unavailable")
            return 2
        print(f"aioquic {getattr(aioquic, '__version__', 'unknown')}")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    target = (host, port)

    try:
        if ns.connect_relay:
            transcript, negotiation = _perform_connect_relay_exchange(target=target, ns=ns)
            write_json("INTEROP_TRANSCRIPT_PATH", transcript)
            write_json("INTEROP_NEGOTIATION_PATH", negotiation)
            print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
            body_ok = transcript["response"]["body"] == f"echo:{ns.body}"
            return 0 if transcript["tunnel"]["connect_status"] == 200 and transcript["response"]["status"] == 200 and body_ok else 1

        transcript, negotiation, ticket, new_token = _perform_single_exchange(
            target=target,
            ns=ns,
            session_ticket=None,
            new_token=None,
            zero_rtt=False,
        )

        resumption = env_flag("INTEROP_ENABLE_RESUMPTION")
        zero_rtt = env_flag("INTEROP_ENABLE_ZERO_RTT")
        if resumption:
            if ticket is None:
                transcript["quic"]["resumption_seeded"] = False
                transcript["quic"]["resumption_attempted"] = False
                transcript["quic"]["zero_rtt_attempted"] = False
                negotiation["resumption_used"] = False
                negotiation["early_data_requested"] = False
                negotiation["early_data_accepted"] = False
            else:
                transcript, negotiation, _, _ = _perform_single_exchange(
                    target=target,
                    ns=ns,
                    session_ticket=ticket,
                    new_token=new_token,
                    zero_rtt=zero_rtt,
                )
                transcript["quic"]["resumption_seeded"] = True
                transcript["quic"]["resumption_attempted"] = True
                transcript["quic"]["zero_rtt_attempted"] = bool(zero_rtt)
        else:
            transcript["quic"]["resumption_seeded"] = ticket is not None
            transcript["quic"]["resumption_attempted"] = False
            transcript["quic"]["zero_rtt_attempted"] = False

        write_json("INTEROP_TRANSCRIPT_PATH", transcript)
        write_json("INTEROP_NEGOTIATION_PATH", negotiation)
        print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
        if ns.response_trailers:
            trailers = {tuple(item) for item in transcript["response"].get("trailers", [])}
            ok = transcript["response"]["status"] == 200 and transcript["response"]["body"] == "ok" and ("x-trailer-one", "yes") in trailers and ("x-trailer-two", "done") in trailers
            return 0 if ok else 1
        if ns.content_coding:
            vary = str(transcript["response"].get("vary") or "").lower()
            ok = transcript["response"]["status"] == 200 and transcript["response"].get("content_encoding") == "gzip" and "accept-encoding" in vary and transcript["response"].get("decoded_body") == "compress-me"
            return 0 if ok else 1
        return 0 if transcript["response"]["status"] == 200 else 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


