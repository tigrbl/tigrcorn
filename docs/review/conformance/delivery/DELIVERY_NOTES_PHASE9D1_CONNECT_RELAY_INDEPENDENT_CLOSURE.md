# Delivery notes — Phase 9D1 CONNECT relay independent closure

This checkpoint closes the HTTP/3 CONNECT relay strict-target artifact gap by overlaying a passing `aioquic` CONNECT relay run into the 0.3.8 working release root.

RFC 9110 §9.3.6 CONNECT relay is now green across HTTP/1.1, HTTP/2, and HTTP/3. The package remains non-promotable because the HTTP/3 trailer-fields and content-coding scenarios are still non-passing.
