# Delivery notes — certification environment freeze

This checkpoint freezes the strict-promotion installation contract, adds a certification-environment bundle, and wires the requirement into a release-workflow guard and a local checkpoint wrapper.

It does **not** claim that the package is already strict-target green; it only closes the environment-provisioning ambiguity that previously allowed the remaining HTTP/3 third-party scenarios to run without the required extras installed.
