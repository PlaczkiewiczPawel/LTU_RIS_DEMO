function timeSamples = buildTransmitFrame(frameNumber, cfg, params)
%BUILDTRANSMITFRAME Create one column-vector OFDM frame before power scaling.

    arguments
        frameNumber (1,1) double {mustBeInteger, mustBeNonnegative}
        cfg (1,1) struct
        params (1,1) struct
    end
    if frameNumber >= cfg.ofdm.numFrames
        error('OFDM:FrameNumberOutOfRange', ...
            'frameNumber must be smaller than cfg.ofdm.numFrames.');
    end

    p = cfg.ofdm;
    data = params.constellation(randi(4, p.numUsedSubcarriers, p.numSymbols));
    data(p.pilotPositions, :) = p.pilotSymbol;

    frameSymbols = params.constellation(params.encodedFrameNumbers(:, frameNumber+1));
    frameSymbols = frameSymbols(:);
    data(p.framePositions, :) = repmat(frameSymbols, 1, p.numSymbols);
    symbolNumberSymbols = params.constellation(params.encodedSymbolNumbers);
    symbolNumberSymbols = reshape(symbolNumberSymbols, size(params.encodedSymbolNumbers));
    data(p.symbolPositions, :) = symbolNumberSymbols;

    frequencyGrid = complex(zeros(p.fftLength, p.numSymbols));
    frequencyGrid(2:p.numUsedSubcarriers/2+1, :) = data(params.positiveDataRows, :);
    frequencyGrid(p.fftLength-p.numUsedSubcarriers/2+1:p.fftLength, :) = ...
        data(params.negativeDataRows, :);

    usefulSamples = ifft(frequencyGrid, p.fftLength, 1) * sqrt(p.numUsedSubcarriers);
    withPrefix = [
        usefulSamples(end-p.cyclicPrefixLength+1:end, :);
        usefulSamples
    ];
    timeSamples = withPrefix(:);
end
