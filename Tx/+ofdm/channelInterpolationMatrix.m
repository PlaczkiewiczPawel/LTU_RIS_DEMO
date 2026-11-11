function matrix = channelInterpolationMatrix(numSubcarriers, pilotPositions)
%CHANNELINTERPOLATIONMATRIX Precompute linear pilot interpolation weights.

    pilotPositions = pilotPositions(:);
    matrix = interp1(pilotPositions, eye(numel(pilotPositions)), ...
        (1:numSubcarriers).', 'linear', 'extrap');
end
