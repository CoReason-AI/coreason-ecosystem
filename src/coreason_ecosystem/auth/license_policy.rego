package coreason.governance.license

# Default deny
default is_sovereign = false

# Allow if the JWT explicitly contains the required entitlement and is not expired
is_sovereign {
    # Verify expiration (OPA time is in nanoseconds, input.exp is usually seconds)
    input.exp > (time.now_ns() / 1000000000)
    
    # Check for specific IP sovereignty entitlement
    some i
    input.entitlements[i] == "IP_SOVEREIGNTY_EXCEPTION"
}
