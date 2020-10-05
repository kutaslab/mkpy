function epset2fitgridh5(expname,varargin)
% epset2fitgridh5()-Create and save to disk h5 for fitgrid from EEGLAB
% epoched set files that contatin EEG.epoch structure%

% Usage:
%  >> epset2fitgridh5(expname,varargin)
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
%   setfilepath    = the directory of input set file, [default: current directory]
%
%  Global Variables:
%   VERBLEVEL = matlabMK level of verbosity (i.e., tells functions
%               how much to report about what they're doing during
%               runtime) set by the optional function argument 'verblevel'

% >> expname = 'for_matlab';
% >> filepath = '/mnt/cube/home/wec017/mkh52set_local/output';
%
% >> epset2fitgridh5(expname,'tbtype',tbtype,'evtype',evtype,'setfilepath',filepath);
%
%
% Author: Wen-Hsuan Chan
% KutasLab 01/2019

addpath(genpath('/mnt/cube/home/wec017/mkh52set_remote/functions'))

% %Input Parser
p = inputParser;
%Note: the order of the required arguments needs to match precisely their
%order in the function definition (which is also the order used by p.parse
%below)
p.addRequired('expname',@ischar);
p.addParamValue('verblevel',2,@(x) x>=0);
p.addParamValue('setfilepath',[],@(x) ischar(x) | iscell(x));

p.parse(expname,varargin{:});
global VERBLEVEL
VERBLEVEL=p.Results.verblevel;
%

%Show settings of all arguments
if VERBLEVEL>0
    fprintf('epset2fitgridh5 argument values:\n');
    disp(p.Results);
end

if ~isempty(p.Results.setfilepath)
    setfilepath = p.Results.setfilepath;
    fileList = dir([setfilepath,'/',expname,'*_ep.set']);
else
    fileList = dir([expname,'*_ep.set']);
end;


sub_sc=[];sub_eegdata_long=[];s_idx=[];
ev_count=0;
for f=1:length(fileList),
    setfname = fileList(f).name;
    if ~isempty(p.Results.setfilepath)
        setfilepath = p.Results.setfilepath;
        EEG = pop_loadset('filename',setfname,'filepath',setfilepath);
    else
        EEG = pop_loadset('filename',setfname);
    end
    
    if isempty(EEG.epoch),
        VerbReport(sprintf('%s\n%s','This file does not contain epochs',...
            'Please check your procedures of creating EEG.epoch'),2,VERBLEVEL);
        break;
    end
    
    chn_list = struct2table(EEG.chanlocs);
    chn_list = chn_list.labels;
    dat = EEG.epoch;
    % unique epoch_idx across sub
    for r = 1:size(dat,1),
        dat(r).event = dat(r).event+ev_count;
    end;
    tb=[];tb = struct2table(dat);
    if sum(sum(ismissing(tb)))
               VerbReport(sprintf('%s\n%s','There is missing data',...
            'Please check your EEG.epoch and remove columns that you will not use for Fitgrid'),2,VERBLEVEL);
    end 
    tVar=[]; fn = fieldnames(EEG.epoch);for i=1:length(fn);tVar{i} = class(eval(['EEG.epoch.',fn{i}]));end
    sz = size(EEG.data);
    eegdata_long = reshape(EEG.data,sz(1),sz(2)*sz(3))';
    eegtime_long = repmat(EEG.times',sz(3),1);
    s_idx = [s_idx;ones(size(eegdata_long,1),1)*f];
    tb = repmat(tb,sz(2),1);
    tb = sortrows(tb,{'event'},{'ascend'});
    sc = struct2cell(table2struct(tb))';
    
    % loop subject
    sub_sc = [sub_sc;sc];    
    ev_count = ev_count + sz(3);
    sub_eegdata_long = [sub_eegdata_long;eegdata_long];
end

% this structure has 1x 1 dimension, its .h5 is reable by pandas
inStruct = [];
inStruct.Epoch_idx =  cast(cell2mat(sub_sc(:,1)),'int64');
inStruct.Time = cast(repmat(eegtime_long,[f 1]),'int64');
inStruct.file_idx =  cast(s_idx,'int64');
n = fieldnames(EEG.epoch);

% find char column, and max str size
char_idx = find(strcmp(tVar,'char'));
max_str = size(char(sub_sc(1,char_idx)),2);
chr = blanks(max_str+1)';
chr_2 = repmat(chr,[1 size(sub_sc,1)]);
for i = 1:length(n),
    if strcmp(tVar{i},'char')
        current_char_s = size(char(cellstr(sub_sc(:,i))),2);
        current_char_array = chr_2;
        current_char_array(1:current_char_s,:) = char(cellstr(sub_sc(:,i)))';
        inStruct.(n{i}) = current_char_array;
    else
        inStruct.(n{i}) = cast(cell2mat(sub_sc(:,i)),char(tVar{i}));
    end
end;
% put index and data together
for ii = 1:length(chn_list)
    inStruct.(chn_list{ii}) = sub_eegdata_long(:,ii)';
end

% % Export to hdf5
if isempty(p.Results.setfilepath)
    fileName = 'eeglabset_epoch.h5';
else
    fileName = [setfilepath,'/','eeglabset_epoch_test.h5'];
end;

DATASET = 'epochs';
file = H5F.create (fileName, 'H5F_ACC_TRUNC',...
    'H5P_DEFAULT', 'H5P_DEFAULT');

sFields = fieldnames(inStruct);
f=0;type_size=[];type_string=[];type_id_list=[];
for sf = sFields.'
    f = f+1;
    data_type_option = class(inStruct(1).(char(sf)));
    switch(data_type_option)
        case 'double'
            datatype = 'H5T_IEEE_F64LE';
        case 'single'
            datatype = 'H5T_IEEE_F32LE';
        case 'uint64'
            datatype = 'H5T_STD_U64LE';
        case 'int64'
            datatype = 'H5T_STD_I64LE';
        case 'uint32'
            datatype = 'H5T_STD_U32LE';
        case 'int32'
            datatype = 'H5T_STD_I32LE';
        case 'uint16'
            datatype = 'H5T_STD_U16LE';
        case 'int16'
            datatype = 'H5T_STD_I16LE';
        case 'uint8'
            datatype = 'H5T_STD_U8LE';
        case 'int8'
            datatype = 'H5T_STD_I8LE';
        case 'char'
            datatype = 'H5T_C_S1';
        case 'cell'
            datatype = 'H5T_C_S1';
        otherwise
            error('Unrecognized Data Type...');
    end
    type_string{f} = datatype;
    type_id = H5T.copy(char(datatype));
    type_id_list = [type_id_list type_id];
    if strcmp(datatype,'H5T_C_S1'),
        h5size = max_str+1;
        H5T.set_size(type_id,h5size);
    end
    type_size(f) = H5T.get_size(type_id);
end

% Computer the offsets to each field. The first offset is always zero.
offset(1)=0;
offset(2:length(sFields))=cumsum(type_size(1:end-1));

% Create the compound datatype for memory.
memtype = H5T.create ('H5T_COMPOUND', sum(type_size));
for fd = 1:length(sFields),
    H5T.insert (memtype,...
        sFields{fd},offset(fd),type_id_list(fd));
end

% Create the compound datatype for the file.  Because the standard
% types we are using for the file may have different sizes than
% the corresponding native types, we must manually calculate the
% offset of each member.
%
filetype = H5T.create ('H5T_COMPOUND', sum(type_size));
for fd = 1:length(sFields),
    H5T.insert (filetype,...
        sFields{fd},offset(fd),type_id_list(fd));
end

% Create dataspace.  Setting maximum size to [] sets the maximum
% size to be the current size.
space = H5S.create_simple (1,fliplr(length(eval(['inStruct.',sFields{1}]))), []);
dset = H5D.create(file, DATASET, filetype, space, 'H5P_DEFAULT');
H5D.write (dset, memtype, 'H5S_ALL', 'H5S_ALL', 'H5P_DEFAULT', inStruct);

% Close and release resources.
H5D.close (dset);
H5S.close (space);
H5T.close (filetype);
H5F.close (file);

