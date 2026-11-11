function params = derivedParameters(cfg)
%DERIVEDPARAMETERS Calculate immutable indices used by transmitter and receiver.

    validateConfig(cfg);
    p = cfg.ofdm;
    params.symbolLength = p.fftLength + p.cyclicPrefixLength;
    params.samplesPerFrame = params.symbolLength * p.numSymbols;
    params.sampleIndex = (0:params.samplesPerFrame-1).';
    params.constellation = [1+1i, 1-1i, -1+1i, -1-1i] / sqrt(2);

    params.usedBins = [
        p.fftLength-p.numUsedSubcarriers/2+1:p.fftLength, ...
        2:p.numUsedSubcarriers/2+1
    ];
    params.positiveDataRows = p.numUsedSubcarriers/2+1:p.numUsedSubcarriers;
    params.negativeDataRows = 1:p.numUsedSubcarriers/2;

    params.frequencyShifts = -cfg.receiver.integerOffsetRange: ...
        cfg.receiver.integerOffsetRange;
    params.candidateBins = mod(params.usedBins.' - ...
        params.frequencyShifts - 1, p.fftLength) + 1;
    params.interpolationMatrix = ofdm.channelInterpolationMatrix( ...
        p.numUsedSubcarriers, p.pilotPositions);

    params.encodedSymbolNumbers = 1 + de2bi( ...
        1:p.numSymbols, numel(p.symbolPositions), 4, 'left-msb').';
    params.encodedFrameNumbers = 1 + de2bi( ...
        0:p.numFrames-1, numel(p.framePositions), 4, 'left-msb').';
end
