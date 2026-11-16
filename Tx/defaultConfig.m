function cfg = defaultConfig()
%DEFAULTCONFIG Return a documented configuration for the OFDM experiment.

    % Radio and transport
    cfg.radio.platform          = 'N200/N210/USRP2';
    cfg.radio.masterClockRate   = 100e6;
    cfg.radio.centerFrequency   = 5.53e9;
    cfg.radio.samplingFrequency = 1e6;
    cfg.radio.txGain            = 20;
    cfg.radio.rxGain            = 18;
    cfg.radio.txIPAddress       = '192.168.100.2';
    cfg.radio.rxIPAddress       = '192.168.100.201';
    cfg.radio.samplesPerRead    = 3620;
    cfg.radio.discoveryAttempts = 10;
    cfg.radio.retryDelaySeconds = 1;
    cfg.radio.clockSource       = 'External'; % Shared 10 MHz reference on TX/RX

    % OFDM waveform
    cfg.ofdm.fftLength          = 128;
    cfg.ofdm.cyclicPrefixLength = 32;
    cfg.ofdm.numUsedSubcarriers = 50;
    cfg.ofdm.numSymbols         = 20;
    cfg.ofdm.numFrames          = 20000;
    cfg.ofdm.pilotPositions     = [1, 6, 11, 16, 21, 30, 35, 40, 45, 50];
    cfg.ofdm.framePositions     = [2, 5, 10, 15, 20, 31, 36, 41, 46, 49];
    cfg.ofdm.symbolPositions    = [7, 12, 17, 22, 29, 34, 39, 44];
    cfg.ofdm.pilotSymbol        = 1 + 1i;

    % Algorithms and presentation
    cfg.receiver.integerOffsetRange      = 3;
    cfg.receiver.minimumTimingMetric     = 0.02;
    cfg.receiver.minimumChannelMagnitude = 1e-10;
    cfg.visualization.enabled            = true;
    cfg.visualization.updateEveryFrames  = 2500;

    % Amplitude division by four is approximately 12 dB power backoff.
    cfg.transmitter.amplitudeScale  = 0.25;
    cfg.transmitter.reportUnderruns = true;

    % Repeatable hardware-free demonstration settings.
    cfg.simulation.randomSeed           = 7;
    cfg.simulation.signalToNoiseRatioDb = 30;
    cfg.simulation.timingOffsetSamples  = 12;
    cfg.simulation.fractionalBinOffset  = 0.15;
    cfg.simulation.integerBinOffset     = 1;

    validateConfig(cfg);
end
