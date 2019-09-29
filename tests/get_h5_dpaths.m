function paths = get_h5_dpaths(hinfo, paths, path, name)
%   Recursive function to fetch slash paths to datasets from hinfo object
%
%   Parameters
%   ----------
%   hinfo : object
%      as returned by h5info(filename);
%   paths : cell array of strings
%      each string is a full slashpath to an h5 dataset
%   path : string
%      slash path to a group
%   name : string
%      as returned by Group.Name 
%
%   Example
%   -------
%      >> hinfo = h5info('myfile.h5')
%      >> dpaths = get_h5_dpaths(hinfo, {}, '','')
%       >> fprintf('%s\n', dpaths)
%
    path = [path, name];
    if (length(hinfo.Groups) > 0)
        for (g = [1: length(hinfo.Groups)])
            paths = get_h5_dpaths(hinfo.Groups(g), ...
                                  paths, path, hinfo.Groups(g).Name);
        end
    else
        if (length(hinfo.Datasets) > 0)
            % fprintf('found datasets\n')
            for (d = [1: length(hinfo.Datasets)])
                paths(length(paths) + 1) = ...
                    cellstr(sprintf('%s/%s\n', path, ...
                                   hinfo.Datasets(d).Name));
            end            
        end
    end

