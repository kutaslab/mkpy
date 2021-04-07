function h52set(h5file,varargin)
% h52set() - Create and save to disk an EEGLAB set file from a
%             Kutaslab h5 file.
%
% Usage:
%  >> h52set(h5file,varargin)
%
% Required Inputs:
%   h5file    = 'name of Kutaslab h5 file'
%
%   NOTE: All file names should be strings and should include the
%   file's path unless the file is in the current working directory.
%
%
% Optional Inputs:
%   verblevel      = an integer specifiying the amount of information you want
%                    this function to provide about what it is doing during runtime.
%                    Options are:
%                      0 - quiet, only show errors, warnings, and EEGLAB reports
%                      1 - stuff anyone should probably know
%                      2 - stuff you should know the first time you start working
%                          with a data set (default value)
%                      3 - stuff that might help you debug (show all reports)
%   sbjct_infofile = name of a text file or a cell array of text file names
%                    containing NUMERIC information about grpjects
%                    in the experiment (e.g., age, working memory span). The
%                    first row of this file should be a header row consisting
%                    of names for each column.  The name of a column can NOT
%                    contain white space (e.g., 'sbjct age' is NOT ok, but
%                    'sbjct_age' would be fine) nor can it contain
%                    parenthesis (e.g., 'sbjct(age)' won't work).
%                    Note, this option must be used with the 'sbject_id'
%                    option described below. (default: [])
%
%
% Outputs:
%   The function writes a set file to disk and the EEGLAB global
%   variable EEG is overwritten to store the new data set. Also,
%   some temporary files are written to the current working
%   directory and deleted.
%
% Global Variables:
%   VERBLEVEL = matlabMK level of verbosity (i.e., tells functions
%               how much to report about what they're doing during
%               runtime) set by the optional function argument 'verblevel'
%
%   SUBJECT   = temporary struct that stores EEG data and cal
%               pulses and some related info
%
%   EEG, ALLEEG = EEGLAB global variables
%
%
% Example:
% >> h5file =   '/home/wec017/h52set/logmet12.h5';
% >> sbjctfile =  '/home/wec017/h52set/test_sbjctages.txt';
% >> h52set(filename)
% >> h52set(h5file,'sbjct_infofile',sbjctfile);
%
% Author:
% Wen-Hsuan Chan (optional inputs based on crw2set.m by David Groppe)
% Kutaslab, 5/2017
%

% addpath(genpath('/mnt/cube/home/wec017/mkh52set_remote/functions'))
addpath(genpath('functions'))

global VERBLEVEL
global grpJECT

global EEG
global ALLEEG

%Input Parser
p = inputParser;
%Note: the order of the required arguments needs to match precisely their
%order in the function definition (which is also the order used by p.parse
%below)
p.addRequired('h5file',@ischar);
p.addParamValue('verblevel',2,@(x) x>=0);
p.addParamValue('sbjct_infofile',[],@(x) ischar(x) | iscell(x));
p.addParamValue('setfilepath',[],@(x) ischar(x) | iscell(x));
p.parse(h5file,varargin{:});

VERBLEVEL=p.Results.verblevel;

%Show settings of all arguments
if VERBLEVEL>0
    fprintf('h52set argument values:\n');
    disp(p.Results);
end


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% I. OPEN H5 FILE USING h5info() & GET EXP INFO AND RECORDING PARAMETERS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% get info of h5file
info = h5info(h5file);
dpaths = get_h5_dpaths(info, {}, '','');
ep_fields=[];
% find epoch table and sort details by subj
sdpaths = sort(dpaths);
idx_epaths = strfind(sdpaths,'/epochs/');
idx_epaths = find(cellfun(@isempty,idx_epaths)==0);
if ~isempty(idx_epaths),
    for ept = 1:length(idx_epaths),
        t2read = sdpaths{idx_epaths(ept)};
        ept_name = regexprep(t2read,'/epochs/','');
        this_eptab = h5read(h5file, t2read);
        [A AI] = sort(this_eptab.data_group(:,:)',1);
        % for EventTable
        for s = 2:size(info.Groups,1),
            idx_sub = strfind(cellstr(A),info.Groups(s).Name(2:end));
            idx_sub = find(cellfun(@isempty,idx_sub)==0);
        end
        
        % transpose if necessary in order to make this_eptab into a table
        z = struct2cell(this_eptab);
        this_eptab_fields = fields(this_eptab);
        cell_this_eptab = cellfun(@size,z,'un',0);
        size_cell_this_eptab = cellfun(@(x)size(x,1),z,'un',0);
        thresh = max(cell2mat(size_cell_this_eptab));
        chk_size_cell_this_eptab = cellfun(@(x) x<thresh,size_cell_this_eptab,'UniformOutput',false);
        tt = find(cellfun(@(x) x>0,chk_size_cell_this_eptab));
        for tts = 1:length(tt),
            z{tt(tts)}=z{tt(tts)}';
        end
        this_eptab = cell2struct(z,this_eptab_fields);
        tb_this_eptab = struct2table(this_eptab);
        idx_sort = find(cellfun(@(x) strcmpi('data_group',x),this_eptab_fields));
        tb_this_eptab = sortrows(tb_this_eptab,idx_sort);
        ep.(ept_name) = tb_this_eptab;
    end
    ep_fields = fieldnames(ep);
end

for grp=1:size(info.Groups);
    edata=[];eventdata=[];this_sub_ep=[];boundary_idx=[];
    nfilename= sprintf('%s_%s.set',h5file(1:end-3),info.Groups(grp).Name(2:end));
    if isempty(info.Groups(1).Datasets)
        error('Datasets cannot be found or Datasets cannot be found directly under the associated Group. Please check your crw2h5 pipeline')
    end
    % get epoch table info
    if cell2mat(strfind({info.Groups(grp).Datasets(1).Attributes.Name},'json_header'))~=1
        % Get experiment info and recording parameters
        VerbReport('Getting header information', 3, VERBLEVEL);
        dint = [sprintf(info.Groups(grp).Name),'/'];
        idx_dpaths = strfind(dpaths,dint);
        idx_dpaths = find(cellfun(@isempty,idx_dpaths)==0);
        
        hdr_json = info.Groups(grp).Datasets(1).Attributes.Value;
        hdr = loadjson(hdr_json);
        
        % checking channel columns from hdr
        EventTableColNames = [];
        a = fieldnames(hdr.streams);
        col = [];colx=[];
        for i=1:length(a),
            ss = sprintf('%s%s','hdr.streams.',a{i});
            ss = eval(ss);
            if strcmp(ss.source(1:3),'dig');
                col = [col i];
            else
                EventTableColNames{i} = a{i};
                colx = [colx i];
            end
        end
        % check order of EventTableColNames (and also for eventdat)
        % note 20200122: crw_ticks is a correct anchor as each crw
        % (each group) will be saved into each .set
        idx_latency = strfind(EventTableColNames,'crw_ticks');
        
        idx_evcode = strfind(EventTableColNames,'evcodes');
        nEventTableColNames = EventTableColNames;ncolx=colx;
        if ~isempty(idx_latency),
            idx_latency = find(cellfun(@isempty,idx_latency)==0);
            nEventTableColNames{1} = EventTableColNames{idx_latency(1)};
            nEventTableColNames{idx_latency(1)} = EventTableColNames{1};
            ncolx(1) = colx(idx_latency(1));
            ncolx([idx_latency(1)]) = colx(1);
        end;
        if ~isempty(idx_evcode),
            idx_evcode = find(cellfun(@isempty,idx_evcode)==0);
            nEventTableColNames{idx_evcode(1)} = nEventTableColNames{2};
            nEventTableColNames{2} = EventTableColNames{idx_evcode(1)};
            ncolx([2 idx_evcode(1)]) = ncolx([idx_evcode(1) 2]);
        end
        EventTableColNames = nEventTableColNames;
        EventTableColNames{1} = 'latency'; % original crw_ticks
        EventTableColNames{2} = 'type';
        colx = ncolx;
        % % old order keep in case % %         EventTableColNames = {'latency' 'type' 'mklogevcode', 'mklogccode' 'mklogflag' 'mkdblock_ticks'};
        SUBJECT.PARAMS.expdesc = hdr.expdesc;
        SUBJECT.PARAMS.subdesc = hdr.subdesc;
        srate = hdr.samplerate;
        if isempty(srate),
            srate=250;
            VerbReport(sprintf(['sampling rate is assigned to 250Hz']));
        end;
        for block = 1: size(idx_dpaths,2),
            t2read = dpaths{idx_dpaths(block)};
            data = h5read(h5file,t2read);
            column_info = fieldnames(data);
            channel_info = column_info(col:end);
            edat = [];
            % loop data
            for i = 1:length(col),
                edat = [edat;eval(sprintf('data.%s',column_info{col(i)}))'];
            end;
            % loop eventcode
            tmpevents = [];
            for i = 1:length(colx),
                tmpevents = [tmpevents eval(sprintf('data.%s',column_info{colx(i)}))];
                %                 if i==colx(2),
                %                     tmpevents = tmpevents+1;
                %                 end;
                %                tmpevents=[tmpevents eval(sprintf('data.%s',column_info{1}))+1];
            end;
            edata = [edata edat];
            eventdata= [eventdata;tmpevents];
            boundary_idx = [boundary_idx;length(eventdata(:,1))];
            
        end; % end_block
        ep_info = eventdata;
        
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % II. LOAD INFORMATION ABOUT PARTICIPANT FROM TEXT FILE(S) [OPTIONAL]
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        if ~isempty(p.Results.sbjct_infofile)
            sbjct_id = info.Groups(grp).Name;
            sbjct_id = sbjct_id(2:end);
            VerbReport(' ',1, VERBLEVEL);
            n_ep = size(ep_info,1);
            if iscell(p.Results.sbjct_infofile)
                n_file = length(p.Results.sbjct_infofile);
                for dd = 1:n_file, % sbjct_infofile is cell array of text file names
                    [new_info, info_names]=add_sbjct_info(p.Results.sbjct_infofile{dd},sbjct_id);
                    new_info=repmat(new_info,n_ep,1);
                    ep_info=[ep_info new_info];
                    for dg=1:length(info_names),
                        EventTableColNames{length(EventTableColNames)+1}= ...
                            info_names{dg};
                        log_LongDesc{length(log_LongDesc)+1}=info_names{dg};
                    end
                end
            else %presumably sbjct_infofile is just a string name of a text file
                [new_info, info_names] = add_sbjct_info(p.Results.sbjct_infofile,sbjct_id);
                new_info = repmat(new_info,n_ep,1);
                ep_info=[ep_info new_info];
                for dg=1:length(info_names),
                    EventTableColNames{length(EventTableColNames)+1} = ...
                        info_names{dg};
                end
            end
        end
        clear n_file new_info info_names n_ep
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % III. Find Epoch info for a given sub  (info.Groups.Name)
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        if ~isempty(ep_fields),
            for eps = 1:size(ep_fields,1)
                idx_sub = cellstr(ep.(ep_fields{eps}).data_group);
                idx_sub = find(cellfun(@(x) strcmpi(info.Groups(grp).Name(2:end),x),idx_sub));
                this_sub_ep.(ep_fields{eps}) = ep.(ep_fields{eps})(idx_sub,:);
            end
        end
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % IV. CREATE EEGLAB SET FILE AND SAVE TO DISK
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        
        SUBJECT.DATA.data = edata;
        dimdata = size(edata);
        nchans = dimdata(1);
        
        EEG = pop_importdata( 'dataformat', 'array', 'data', SUBJECT.DATA.data, ...
            'setname', nfilename(1:(length(nfilename)-4)), ...
            'srate',srate, ...
            'subject', SUBJECT.PARAMS.subdesc, ...
            'nbchan', nchans, ...
            'comments', SUBJECT.PARAMS.expdesc, ...
            'pnts',size(SUBJECT.DATA.data,2),...
            'xmin',0);
                
        % check if there is chanloc info
        if isfield(hdr,'apparatus')
            EEG.chanlocs = get_loc(info,hdr,channel_info);
            EEG = pop_chanedit(EEG, 'convert',{'cart2all'});
        else
            EEG.chanlocs = table2struct(cell2table(channel_info,'VariableNames',{'labels'}));
        end
                        
        idx = find(ep_info(:,2)>0);
        idxevent = ep_info(idx,:);
        
        EEG = pop_importevent( EEG, 'event',idxevent,...
            'fields',EventTableColNames,...
            'align', NaN,'timeunit',1/srate,'append', 'no');
        e=0;     
        
        EEG = eeg_checkset( EEG );
        EEG.ref='not specified';
        if isempty(this_sub_ep)
            EEG.mkh5ep=[];
        elseif prod(size(struct2table(this_sub_ep)))==0, % 20200804 update to take care of 0 rows
            EEG.mkh5ep=[];
        else
            EEG.mkh5ep = this_sub_ep;
        end;

        
%         % % 'duration'
%       if do, get plotting errors later on??
%         if ~isfield(EEG.event, 'duration')
%             durarray = num2cell(zeros(1,size(idxevent,1)));
%             [EEG.event(1:size(idxevent,1)).duration] = durarray{:};
%         end

        if ~isempty(boundary_idx),
            for bidx = 1:length(boundary_idx),
                e = e+1;
                EEG.event(length(idxevent(:,1))+e).type = 'boundary';
                EEG.event(length(idxevent(:,1))+e).latency = ep_info(boundary_idx(bidx),1)+1;
%                 % 'Hard' boundary
%                 %  https://sccn.ucsd.edu/wiki/Chapter_03:_Event_Processing#Boundary_events
%                 EEG.event(length(idxevent(:,1))+e).duration = NaN();
                EEG.urevent(length(idxevent(:,1))+e).type = 'boundary';
                EEG.urevent(length(idxevent(:,1))+e).latency = ep_info(boundary_idx(bidx),1)+1;
            end;
        end;
        EEG = eeg_checkset( EEG );
        setfilepath = p.Results.setfilepath;
        if ~isempty(p.Results.setfilepath)
            a = strfind(nfilename,'/');
            if ~isempty(a),
                nfilename = nfilename(a(end)+1:length(nfilename));
            end
            EEG = pop_saveset(EEG,'filename',nfilename,'filepath',setfilepath);
        else
            EEG = pop_saveset(EEG,'filename',nfilename);
        end
    end;
    
end;
