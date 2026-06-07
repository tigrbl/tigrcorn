from __future__ import annotations

import json
from dataclasses import dataclass
import logging
import logging.config
import socket
from logging import Logger
from pathlib import Path
from typing import Any, Mapping

from tigrcorn_config.files import ConfigFileError, load_config_source
from tigrcorn_observability.protocol import make_observability_record


class LoggingConfigError(RuntimeError):
    pass


_ALLOWED_PROFILE_KEYS = {
    'level',
    'structured',
    'access_log',
    'access_log_file',
    'access_log_format',
    'error_log_file',
    'format',
    'stream',
    'syslog_app_name',
    'syslog_enterprise_id',
    'syslog_msgid',
    'syslog_procid',
    'use_colors',
}


@dataclass(slots=True)
class ResolvedLoggingConfig:
    level: str = 'info'
    structured: bool = False
    access_log: bool = True
    access_log_file: str | None = None
    access_log_format: str | None = None
    error_log_file: str | None = None
    format: str = 'default'
    stream: bool = True
    syslog_app_name: str = 'tigrcorn'
    syslog_enterprise_id: int = 32473
    syslog_msgid: str = '-'
    syslog_procid: str = '-'
    use_colors: bool | None = None
    log_config: str | None = None
    dict_config: dict[str, Any] | None = None
    explicit_fields: tuple[str, ...] = ()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for key in ('event', 'peer', 'method', 'path', 'proto', 'status', 'result', 'trace_id', 'span_id'):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, sort_keys=True)


class ColorFormatter(logging.Formatter):
    _COLORS = {
        logging.DEBUG: '\x1b[36m',
        logging.INFO: '\x1b[32m',
        logging.WARNING: '\x1b[33m',
        logging.ERROR: '\x1b[31m',
        logging.CRITICAL: '\x1b[35m',
    }
    _RESET = '\x1b[0m'

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self._COLORS.get(record.levelno)
        if not color:
            return message
        return f'{color}{message}{self._RESET}'


class RFC5424Formatter(logging.Formatter):
    _SEVERITY = {
        logging.DEBUG: 7,
        logging.INFO: 6,
        logging.WARNING: 4,
        logging.ERROR: 3,
        logging.CRITICAL: 2,
    }

    def __init__(
        self,
        *,
        app_name: str = 'tigrcorn',
        procid: str = '-',
        msgid: str = '-',
        enterprise_id: int = 32473,
    ) -> None:
        super().__init__()
        self.app_name = app_name or '-'
        self.procid = procid or '-'
        self.msgid = msgid or '-'
        self.enterprise_id = enterprise_id
        self.hostname = socket.gethostname() or '-'

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z')
        if timestamp.endswith('+0000'):
            timestamp = timestamp[:-5] + 'Z'
        priority = 8 + self._SEVERITY.get(record.levelno, 6)
        structured_data = self._structured_data(record)
        return (
            f'<{priority}>1 {timestamp} {self._nil_safe(self.hostname)} '
            f'{self._nil_safe(self.app_name)} {self._nil_safe(self.procid)} '
            f'{self._nil_safe(self.msgid)} {structured_data} {record.getMessage()}'
        )

    def _structured_data(self, record: logging.LogRecord) -> str:
        pairs: list[str] = []
        for key in ('event', 'peer', 'method', 'path', 'proto', 'status', 'result', 'trace_id', 'span_id'):
            value = getattr(record, key, None)
            if value is not None:
                pairs.append(f'{key}="{self._escape_param(str(value))}"')
        if not pairs:
            return '-'
        return f'[tigrcorn@{self.enterprise_id} {" ".join(pairs)}]'

    @staticmethod
    def _escape_param(value: str) -> str:
        return value.replace('\\', '\\\\').replace('"', '\\"').replace(']', '\\]')

    @staticmethod
    def _nil_safe(value: str) -> str:
        cleaned = str(value).strip()
        return cleaned if cleaned else '-'


class CloseAfterEmitFileHandler(logging.Handler):
    terminator = '\n'

    def __init__(self, path: str) -> None:
        super().__init__()
        self.baseFilename = str(Path(path))
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            with open(self.baseFilename, 'a', encoding='utf-8') as stream:
                stream.write(message + self.terminator)
        except Exception:
            self.handleError(record)


class AccessLogger:
    def __init__(self, logger: Logger, *, enabled: bool = True, fmt: str | None = None) -> None:
        self.logger = logger
        self.enabled = enabled
        self.fmt = fmt or '{peer} "{method} {path} {proto}" {status}'
        self.observability_records: list[dict[str, Any]] = []

    def _peer(self, client: tuple[str, int] | None) -> str:
        return f"{client[0]}:{client[1]}" if client else '-'

    def log_http(
        self,
        client: tuple[str, int] | None,
        method: str,
        path: str,
        status: int,
        proto: str,
        *,
        request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] | None = None,
        tls_version: str | None = None,
        alpn: str | None = None,
        transport: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        peer = self._peer(client)
        message = self.fmt.format(peer=peer, method=method, path=path, status=status, proto=proto)
        observability = self._http_observability_record(
            peer=peer,
            method=method,
            path=path,
            status=status,
            proto=proto,
            request_headers=request_headers,
            tls_version=tls_version,
            alpn=alpn,
            transport=transport,
        )
        self.observability_records.append(observability)
        self.logger.info(
            message,
            extra={
                'event': 'access.http',
                'peer': peer,
                'method': method,
                'path': path,
                'status': status,
                'proto': proto,
                'observability': observability,
            },
        )

    def log_ws(self, client: tuple[str, int] | None, path: str, result: str) -> None:
        if not self.enabled:
            return
        peer = self._peer(client)
        message = f'{peer} "WEBSOCKET {path}" {result}'
        observability = make_observability_record(
            kind='event',
            name=f'websocket.{result}',
            labels={
                'protocol': 'websocket',
                'transport': 'tcp',
                'lifecycle': result,
                'peer': peer,
                'path': path,
            },
            attributes={'result': result},
        )
        self.observability_records.append(observability)
        self.logger.info(
            message,
            extra={
                'event': 'access.websocket',
                'peer': peer,
                'path': path,
                'result': result,
                'observability': observability,
            },
        )

    def _http_observability_record(
        self,
        *,
        peer: str,
        method: str,
        path: str,
        status: int,
        proto: str,
        request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] | None,
        tls_version: str | None,
        alpn: str | None,
        transport: str | None,
    ) -> dict[str, Any]:
        protocol = _protocol_from_http_proto(proto)
        labels: dict[str, Any] = {
            'protocol': protocol,
            'transport': transport or ('quic' if protocol == 'http3' else 'tcp'),
            'peer': peer,
            'path': path,
        }
        if tls_version is not None:
            labels['tls_version'] = tls_version
        if alpn is not None:
            labels['alpn'] = alpn
        return make_observability_record(
            kind='event',
            name='http.request',
            labels=labels,
            attributes={
                'headers': _headers_to_mapping(request_headers or ()),
                'method': method,
                'status': int(status),
            },
        )


def _protocol_from_http_proto(proto: str) -> str:
    normalized = str(proto).lower()
    if normalized.endswith('/3'):
        return 'http3'
    if normalized.endswith('/2'):
        return 'http2'
    return 'http1'


def _headers_to_mapping(headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers:
        result[name.decode('latin1').lower()] = value.decode('latin1', 'replace')
    return result


def _coerce_level(level: str) -> int:
    return getattr(logging, str(level).upper(), logging.INFO)


def _file_handler(path: str, formatter: logging.Formatter) -> logging.Handler:
    handler = CloseAfterEmitFileHandler(path)
    handler.setFormatter(formatter)
    return handler


def _coerce_profile_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise LoggingConfigError(f'logging profile {name!r} must be a boolean')


def load_logging_profile(path: str | Path) -> dict[str, Any]:
    try:
        payload = load_config_source(path)
    except ConfigFileError as exc:
        raise LoggingConfigError(str(exc)) from exc
    if 'logging' in payload and isinstance(payload['logging'], Mapping):
        payload = dict(payload['logging'])
    if not isinstance(payload, Mapping):
        raise LoggingConfigError('log_config must resolve to a mapping or a top-level logging mapping')
    if 'version' in payload:
        return {'dict_config': dict(payload)}
    unknown = sorted(set(payload) - _ALLOWED_PROFILE_KEYS)
    if unknown:
        raise LoggingConfigError(f'log_config contains unsupported keys: {unknown}')
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {'structured', 'access_log', 'stream', 'use_colors'}:
            result[key] = _coerce_profile_bool(key, value)
        elif key in {
            'level',
            'access_log_file',
            'access_log_format',
            'error_log_file',
            'format',
            'syslog_app_name',
            'syslog_procid',
            'syslog_msgid',
        }:
            if value is not None and not isinstance(value, str):
                raise LoggingConfigError(f'logging profile {key!r} must be a string or null')
            result[key] = value
        elif key == 'syslog_enterprise_id':
            if not isinstance(value, int) or value <= 0:
                raise LoggingConfigError("logging profile 'syslog_enterprise_id' must be a positive integer")
            result[key] = value
    if result.get('format') not in {None, 'default', 'json', 'rfc5424'}:
        raise LoggingConfigError("logging profile 'format' must be one of default, json, or rfc5424")
    return result


def resolve_logging_config(level: str = 'info', *, config: Any | None = None) -> ResolvedLoggingConfig:
    resolved = ResolvedLoggingConfig(level=level)
    if config is None:
        return resolved

    explicit_fields = tuple(sorted(set(getattr(config, 'explicit_fields', []) or ())))
    log_config_path = getattr(config, 'log_config', None)
    if log_config_path:
        file_profile = load_logging_profile(log_config_path)
        for key, value in file_profile.items():
            if hasattr(resolved, key):
                setattr(resolved, key, value)
        resolved.log_config = str(log_config_path)

    source_fields = (
        'level',
        'structured',
        'access_log',
        'access_log_file',
        'access_log_format',
        'error_log_file',
        'use_colors',
    )
    if not log_config_path:
        for field_name in source_fields:
            value = getattr(config, field_name, getattr(resolved, field_name))
            setattr(resolved, field_name, value)
    else:
        for field_name in explicit_fields:
            if field_name in source_fields:
                setattr(resolved, field_name, getattr(config, field_name, getattr(resolved, field_name)))

    resolved.explicit_fields = explicit_fields
    return resolved


def validate_logging_contract(config: Any | None) -> None:
    if config is None:
        return
    if getattr(config, 'log_config', None):
        resolve_logging_config(getattr(config, 'level', 'info'), config=config)


def _stream_formatter(*, resolved: ResolvedLoggingConfig, use_colors: bool) -> logging.Formatter:
    if resolved.format == 'rfc5424':
        return RFC5424Formatter(
            app_name=resolved.syslog_app_name,
            procid=resolved.syslog_procid,
            msgid=resolved.syslog_msgid,
            enterprise_id=resolved.syslog_enterprise_id,
        )
    structured = resolved.structured or resolved.format == 'json'
    if structured:
        return JSONFormatter()
    if use_colors:
        return ColorFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    return logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')


def configure_logging(level: str = 'info', *, config: Any | None = None) -> logging.Logger:
    resolved = resolve_logging_config(level, config=config)
    if resolved.dict_config is not None:
        logging.config.dictConfig(resolved.dict_config)
        logger = logging.getLogger('tigrcorn')
        if 'level' in resolved.explicit_fields:
            logger.setLevel(_coerce_level(resolved.level))
        return logger

    logger = logging.getLogger('tigrcorn')
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    logger.setLevel(_coerce_level(resolved.level))
    logger.propagate = False

    if resolved.stream:
        stream_handler = logging.StreamHandler()
        enable_colors = resolved.use_colors
        if enable_colors is None:
            stream = getattr(stream_handler, 'stream', None)
            enable_colors = bool(getattr(stream, 'isatty', lambda: False)())
        stream_handler.setFormatter(_stream_formatter(resolved=resolved, use_colors=bool(enable_colors)))
        logger.addHandler(stream_handler)

    file_formatter: logging.Formatter = _stream_formatter(resolved=resolved, use_colors=False)
    if resolved.access_log_file:
        logger.addHandler(_file_handler(resolved.access_log_file, file_formatter))
    if resolved.error_log_file and resolved.error_log_file != resolved.access_log_file:
        logger.addHandler(_file_handler(resolved.error_log_file, file_formatter))

    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(_stream_formatter(resolved=resolved, use_colors=False))
        logger.addHandler(stream_handler)

    return logger
