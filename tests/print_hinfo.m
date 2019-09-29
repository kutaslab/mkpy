function print_hinfo(hinfo, path, name)
    path = [path, name];
    if (length(hinfo.Groups) > 0)
        for (g = [1: length(hinfo.Groups)])
            print_hinfo(hinfo.Groups(g), path, hinfo.Groups(g).Name)
        end
    else
        if (length(hinfo.Datasets) > 0)
            % fprintf('found datasets\n')
            for (d = [1: length(hinfo.Datasets)])
                fprintf('%s/%s\n', path, hinfo.Datasets(d).Name)
            end
        end
    end

