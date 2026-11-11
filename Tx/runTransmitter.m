%% Hardware OFDM transmitter
cfg = defaultConfig();
params = ofdm.derivedParameters(cfg);

ofdm.discoverRadio(cfg.radio.txIPAddress, cfg);
tx = ofdm.createTransmitter(cfg);
cleanupTx = onCleanup(@() release(tx)); %#ok<NASGU>

rng('shuffle');
fprintf('Transmitting continuously at %.3f GHz. Press Ctrl+C to stop.\n', ...
   cfg.radio.centerFrequency / 1e9);

% Prepare the transmitter for continuous frame streaming.
transmittedFrameCount = 0;
while true
   frameNumber = mod(transmittedFrameCount, cfg.ofdm.numFrames);
   % Generate time samples
   timeSamples = ofdm.buildTransmitFrame(frameNumber, cfg, params);
   % Transmit time samples
   underrun = tx(single(cfg.transmitter.amplitudeScale .* timeSamples));
   transmittedFrameCount = transmittedFrameCount + 1;

   if underrun && cfg.transmitter.reportUnderruns
      fprintf('Underrun at transmitted frame %d.\n', transmittedFrameCount);
   end
end
