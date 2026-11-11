function deviceInfo = discoverRadio(ipAddress, cfg)
%DISCOVERRADIO Find a USRP with bounded retries and a useful final error.

    lastError = [];
    for attempt = 1:cfg.radio.discoveryAttempts
        try
            deviceInfo = findsdru(char(ipAddress));
            if ~isempty(deviceInfo) && ...
                    strcmpi(string(deviceInfo(1).Status), "Success")
                return
            end
        catch discoveryError
            lastError = discoveryError;
        end

        if attempt < cfg.radio.discoveryAttempts
            fprintf('Radio %s not found (%d/%d); retrying.\n', ...
                ipAddress, attempt, cfg.radio.discoveryAttempts);
            pause(cfg.radio.retryDelaySeconds);
        end
    end

    if isempty(lastError)
        error('OFDM:RadioNotFound', ...
            'Could not reach the USRP at %s after %d attempts.', ...
            ipAddress, cfg.radio.discoveryAttempts);
    end
    error('OFDM:RadioNotFound', ...
        'Could not reach the USRP at %s after %d attempts. Last error: %s', ...
        ipAddress, cfg.radio.discoveryAttempts, lastError.message);
end
