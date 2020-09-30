function cset2epset(expname,varargin)
% cset2epset()-Create and save to disk EEGLAB epoched set files from EEGLab
% continuous set files that contatin event tables created by h52set.m and
% mkpy package
%
% Usage:
%  >> cset2epset(expname,varargin)
%
% Required Inputs:
%   expname    = name of set file without sub#
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
%   tbtype         = name of event table that the epoching will be based on
%
%   evtype         = name of variable that the epoching anchors on
%   setfilepath    = the directory of input set file, [default: current directory]
%
%  Global Variables:
%   VERBLEVEL = matlabMK level of verbosity (i.e., tells functions
%               how much to report about what they're doing during
%               runtime) set by the optional function argument 'verblevel'
%
% >> expname = 'for_matlab';
% >> evtype = 'critverb_fit';
% >> tbtype = 'short_epochs';
% >> filepath = '/mnt/cube/home/wec017/mkh52set_local/output';
%
% >> cset2epset(expname,'tbtype',tbtype,'evtype',evtype,'setfilepath',filepath);
%
%
% Author: Wen-Hsuan Chan
% KutasLab 01/2018
%

addpath(genpath('/mnt/cube/home/wec017/mkh52set_remote/functions'))

% %Input Parser
p = inputParser;
%Note: the order of the required arguments needs to match precisely their
%order in the function definition (which is also the order used by p.parse
%below)
p.addRequired('expname',@ischar);
p.addParamValue('verblevel',2,@(x) x>=0);
p.addParamValue('evtype',[],@ischar);
p.addParamValue('tbtype',[],@ischar);
p.addParamValue('setfilepath',[],@(x) ischar(x) | iscell(x));
p.parse(expname,varargin{:});

global VERBLEVEL
VERBLEVEL=p.Results.verblevel;
%

%Show settings of all arguments
if VERBLEVEL>0
    fprintf('cset2epset argument values:\n');
    disp(p.Results);
end

if ~isempty(p.Results.setfilepath)
    setfilepath = p.Results.setfilepath;
    fileList = dir([setfilepath,'/',expname,'*.set']);
else
    fileList = dir([expname,'*.set']);
end;

tbtype_sub=[];evtype_sub=[];

for i=1:length(fileList),
    setfname = fileList(i).name;
    setfname2 =[fileList(i).name(1:end-4),'_ep.set'];
    if ~isempty(p.Results.setfilepath)
        setfilepath = p.Results.setfilepath;
        EEG = pop_loadset('filename',setfname,'filepath',setfilepath);
    else
        EEG = pop_loadset('filename',setfname);
    end
    if ~isempty(EEG.epoch)
        VerbReport('This set has epochs already. Remove files w/ epochs from this directory!',2,VERBLEVEL);
        break;
    end

    % request for input of event table and apply to all subjects
    if ~isempty(p.Results.tbtype),
        tbtype = p.Results.tbtype;
    else
        if ~isempty(EEG.mkh5ep),
            if isempty(tbtype_sub),
                prompt= sprintf('%s%s',strjoin(fieldnames(EEG.mkh5ep)),'? Enter the event table: ');
                tbtype_sub = input(prompt,'s');
                y = strjoin(fieldnames(EEG.mkh5ep));
                if isempty(strfind(y,tbtype_sub)),
                    VerbReport('Make sure the entered event table names is correct!',2,VERBLEVEL);
                    break;
                end
            end
            tbtype = tbtype_sub;
        else
            VerbReport(sprintf('%s\n%s','This file does not contain event table(s)',...
                'Please check your procedures of creating mkh5 with mkpy'),2,VERBLEVEL);
            break;
        end
    end
    % get boundary info
    boundary_latency=[];for i=1:size(EEG.event,2), if strcmp(EEG.event(i).type,'boundary')==1, boundary_latency = [boundary_latency;EEG.event(i).latency-1] ;end;end

    latencycol = 'crw_ticks';

    if ~isempty(EEG.mkh5ep)
        tb_names = fieldnames(EEG.mkh5ep);
    else
        VerbReport('Error: No event table in this set file',2,VERBLEVEL);
        break;
    end;
    tb_idx = strcmp(tbtype,tb_names);
    x = eval(sprintf('%s%s','EEG.mkh5ep.',tb_names{tb_idx}));
    
%     % Create a tick column that counts from the beging of this
%     % continuous eeg. Note: this one missed the facts that the dblock_ticks
%     % for the anchor evcode was not the end of the sample of the block....
%     % crw_ticks has the information needed already.
%     dblock_idx = cell2mat(regexp(cellstr(x.dblock_path),'_[\d]'));
%     dblock = cellstr(x.dblock_path(:,dblock_idx+1:end));
%     dblock = cellfun(@char,dblock,'UniformOutput',0); %as char
%     dblock = cellfun(@str2num,dblock,'UniformOutput',0); %as double
%     dblock = cell2mat(dblock);
%     un = unique(dblock);
%     dblock(:,2) = x.dblock_ticks;
%     block_count=[];
%     for u = un(1):un(length(un)),
%         idx = find(dblock(:,1)==u);
%         block_count = [block_count;max(dblock(idx,2))];
%     end
%     un(:,2) =  cumsum([0;block_count(1:end-1)]);
%     for i=1:length(dblock),
%         if dblock(i,1)==un(1,1),
%            dblock(i,3) = dblock(i,2);
%         else
%            dblock(i,3) = un(find(un(:,1)==dblock(i,1)),2)+dblock(i,2);
%         end
%     end
%     x.crw_dblock_ticks = int64(dblock(:,3));
    
    if ~isempty(p.Results.evtype),
        evtype = p.Results.evtype;
    else
        if isempty(evtype_sub),
            prompt = sprintf('Need a list of variable named to make epochs? Y/N [N]: ');
            str = input(prompt,'s');
            if isempty(str)
                str = 'N';
            end
            if strcmp(str,'Y')
                VerbReport(sprintf('%s',strjoin(fieldnames(x))),2,VERBLEVEL);
            end
            prompt = 'Enter the variable name to epoch: ';
            evtype_sub = input(prompt,'s');
            y = strjoin(fieldnames(x));
            if isempty(strfind(y,evtype_sub)),
                VerbReport('Make sure the variable name is correct!',2,VERBLEVEL);
                break;
            end
            evtype = evtype_sub;
        end
    end
    ev_idx = find(strcmp(fieldnames(x),evtype)==1);
    latency_idx = find(strcmp(fieldnames(x),latencycol)==1);
    
    if isempty(ev_idx)
        VerbReport('Error: please make sure if the input type is in the event table',2,VERBLEVEL);
        break;
    end;
    y=x;
    y.Properties.VariableNames{ev_idx} = 'type';
    y.Properties.VariableNames{latency_idx} = 'latency';
    x = [y(:,latency_idx),y(:,ev_idx),x];
    writetable(x,'temp.txt','Delimiter',',');
    
    EEG.event=[];
    EEG = pop_importevent( EEG, 'event','temp.txt','fields',fieldnames(x),'timeunit',1/EEG.srate,'align',NaN,'skipline',1,'delim',',');
    
    % put boundary info back
    for b=1:length(boundary_latency),
        EEG.event(size(EEG.event,2)+1).type='boundary';
        EEG.event(size(EEG.event,2)).latency = boundary_latency(b);
    end;

    
    ep_start = str2num(int2str(x.epoch_match_tick_delta(1)))/EEG.srate;
    ep_end = str2num(int2str(x.epoch_ticks(1)))/EEG.srate;
    
    EEG = pop_epoch( EEG, {}, [ep_start ep_end], 'newname', setfname, 'epochinfo', 'yes');
    EEG = eeg_checkset( EEG );
    
%     % make data type info back
%     % 0701/2020, got errors when 2 events happen in one epoched window ... cell, leave it for now
%     t.Var=[]; fn = fieldnames(x);for i=1:length(fn);t.Var{i} = {class(eval(['x.',fn{i}]))};end  
%     fn2 = fieldnames(EEG.epoch);
%     ep = struct2table(EEG.epoch);
%     s=[];
%     for fd = 2;%:length(fn2)-3,
%         v_name = ['s.',fn2{fd}];
%         if strcmp(t.Var{fd-1},'char') & strcmp(class(eval(['ep.',fn2{fd}])),'double'),
%             eval([v_name,'= cast(num2str(eval([''ep.'',fn2{fd}])),char(t.Var{fd-1}));']);
%         else
%             % one event has more than one trials...
%             if strcmp(class(eval(['ep.',fn2{fd}])),'cell');
%                 %todo
%             end
%             eval([v_name,'= cast(eval([''ep.'',fn2{fd}]),char(t.Var{fd-1}));']);
%         end
%     end;
%     T = struct2table(s);
%     T = [ep(:,1) T ep(:,end-2:end)];
%         
%     EEG.epoch = table2struct(T);
%     EEG = eeg_checkset( EEG );

    if ~isempty(p.Results.setfilepath)
        EEG = pop_saveset(EEG,'filename',setfname2,'filepath',setfilepath);
    else
        EEG = pop_saveset(EEG,'filename',setfname2);
    end
    delete('temp.txt');
end
