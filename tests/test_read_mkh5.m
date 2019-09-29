% from the command line in
% 
%   /home/turbach/TPU_Projects/mkpy/mkpy/tests
% 
% run this like so
%
%   matlab -nodisplay -nojvm -r "test_read_mkh5('data/for_matlab.h5')"
% 

function rval = test_read_mkh5(filename)
    rval = 0; % assume we are OK
    try

        addpath('./jsonlab-1.8')
        filename = 'data/for_matlab.h5';
        % fprintf('File: %s\n', filename);
        hinfo = h5info(filename);
        dpaths = get_h5_dpaths(hinfo, {}, '','');
        
        % fprint('%s\n', dpaths{:})
        
        for dp = 1:length(dpaths)
            % fprintf('reading dpaths %s ...', dpaths{dp})
            % data = h5read(filename, dpaths{dp});
            % fprintf('ok\n')
        end
        
        long_eptab = h5read(filename, '/epochs/long_epochs');
        n_epochs = size(long_eptab.Epoch_idx,1);
        epochs_data = cell(n_epochs,1);
        % for n = 1:n_epochs
        for n = 1:10
            dpath = ['/', long_eptab.dblock_path(:,n)'];
            start = long_eptab.match_tick(n) + ...
                    long_eptab.epoch_match_tick_delta(n) + 1;
            duration = long_eptab.epoch_ticks(n);
            stop = start + duration + 1;
            fprintf('epoch %5d of %d: %s\n', n, n_epochs, dpath)
            data = h5read(filename, dpath);

            % modicum of error checking
            if start <= 0
                fprintf('bad start %d', start)
                1.0 / 0
            end
            if size(data.dblock_ticks,1) < stop
                fprintf('bad stop %d', stop)
                1.0 / 0
            end

            data_fields = fields(data);
            this_epoch = struct();
            for fn = 1:length(data_fields)
                f = data_fields(fn);
                this_data = getfield(data,f{:});
                dclass = class(this_data);
                if strcmp(dclass,'single')
                    this_epoch = setfield(this_epoch, ...
                             f{:}, ...
                             double(this_data(start:stop)));
                else
                    this_epoch = setfield(this_epoch, ...
                             f{:}, ...
                             this_data(start: stop));
                end
            end
            epochs_data{n} = this_epoch;
        end

    catch err
        disp(err)
        rval = -1;
        % quit force
    end   
    %    fprintf('OK\n')
    exit(rval)


