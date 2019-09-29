function paths = get_hinfo(hinfo, paths, path, name)
    path = [path, name];
    if (length(hinfo.Groups) > 0)
        for (g = [1: length(hinfo.Groups)])
            paths = get_hinfo(hinfo.Groups(g), paths, path, hinfo.Groups(g).Name);
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

