# Architecture overview

TigrCorn separates:

1. **listener**
2. **transport session**
3. **logical stream**
4. **protocol adapter**
5. **ASGI connection**

That decomposition lets the public interface remain ASGI-compatible while the internal
transport stack scales from singleplex HTTP/1.1 up to multiplexed HTTP/2, HTTP/3,
QUIC streams, and custom framed transports.
