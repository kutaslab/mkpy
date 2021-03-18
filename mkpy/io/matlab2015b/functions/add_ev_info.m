function [new_info, info_names]=add_ev_info(event_infofile,blf_ev_num)
% add_ev_info()   - Reads information about log events (e.g., if a stimulus
%                   was accurately recalled by the participant after the
%                   experiment) from a text file and stores the information
%                   as a matrix that can be easily added to existing epoch
%                   information in the function crw2set.m.
%
% Usage:
%  >> [new_info, info_names]=add_ev_info(event_infofile,blf_ev_num)
%
% Required Global Variable:
%   VERBLEVEL         = matlabMK level of verbosity (i.e., tells functions
%                        how much to report about what they're doing during
%                        runtime)
% Inputs:
%   event_infofile     = a space or tab delimited text file
%                        containing additional NUMERIC
%                        information about log events.  The first
%                        row of the file is a header line with a
%                        one word description of each column in the
%                        file. Each row below the headerline
%                        corresponds to a different log event.  The
%                        first column of the file specifies the log
%                        event number.  Additional columns
%                        specificy numeric event information (e.g.,
%                        a binary variable indicating if the item
%                        was subsquently recalled, the
%                        participant's estimate of how probable
%                        that stimulus was).  To import non-numeric
%                        information use logitem_info2set.m.
%   blf_ev_num         = a vector of log event numbers indicating
%                        which row of the matrix of blf event
%                        information (from the parent function)
%                        corresponds to which log event.
%
% Outputs:
%   new_info           = a matrix of new event information that can
%                        be appended to the existing blf info
%                        matrix
%   info_names         = a cell array of strings containing the
%                        header information for each column of
%                        event_infofile. The first column of
%                        event_infofile is ignored since the log
%                        event numbers are already in the blf info matrix.
%
%
% Additional Notes:
%
% Don't use parenthesis in column header names.  Matlab interprets
% the name as a function call.
%
% Use NaN to fill cells for codes that don't have a value for a
% particular column
%
% Author:
% David Groppe
% Kutaslab, 8/2009

%%%%%%%%%%%%%%%% REVISION LOG %%%%%%%%%%%%%%%%%
%
% 10/07/09 Function provides a warning if it detects an attempt to import
% non-numeric values.  Non-numeric values should appear as NaN in new_info.
%

global VERBLEVEL

new_info=[];
info_names=[];
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% LOAD INFORMATION ABOUT EACH LOG EVENT FROM A TEXT FILE
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
VerbReport(sprintf('Getting additional information about log events from %s', ...
    event_infofile), 1, VERBLEVEL);
[ev_fid, message]=fopen(event_infofile,'r');
if (ev_fid==-1)
    fprintf('*************** ERROR ******************\n');
    fprintf('Cannot open file %s.\n',event_infofile);
    fprintf('According to fopen: %s.\n',message);
    fprintf('Aborting import of additional log event information.\n');
    file_ev_info=[];
else
    %read column headers
    txtline = [];
    txtline = fgetl(ev_fid);
    if (txtline==-1)
        fprintf('*************** ERROR ******************\n');
        fprintf('File %s is empty.\n',ev_fid);
        fprintf('Aborting import of additional log event information.\n');
        file_ev_info=[];
    else
        
        %Read column header
        clear ev_col_hdrs;
        [ev_col_hdrs{1}, rmndr]=strtok(txtline);
        col_ct=1;
        fprintf('Event number column is: %s\n',ev_col_hdrs{1});
        while ~isempty(rmndr)
            col_ct=col_ct+1;
            [ev_col_hdrs{col_ct}, rmndr]=strtok(rmndr);
            fprintf('Column %d is: %s\n',col_ct,ev_col_hdrs{col_ct});
        end
        
        %Read event information
        row_ct=1;
        while ~feof(ev_fid)
            txtline = fgetl(ev_fid);
            col_ct=1;
            while ~isempty(txtline)
                [neo_val, txtline]=strtok(txtline);
                file_ev_info(row_ct,col_ct)=str2double(neo_val); %events that
                %do not have a value for that column should be represented as NaN
                if isempty(str2num(neo_val))
                    watchit(sprintf(['Event info file %s appears to have a non-numeric entry at Row #%d, Column %s.\n', ...
                        'When using crw2set only numeric values are permitted.  Use logitem_info2set.m for non-numeric values.'], ...
                        event_infofile,row_ct+1,ev_col_hdrs{col_ct}));
                end
                col_ct=col_ct+1;
            end
            row_ct=row_ct+1;
        end
        
        %Check to make sure each event only occurs once:
        [uni, uni_id]=unique(file_ev_info(:,1),'first'); %First column is
        %assumed to be the log event number
        if length(uni)~=size(file_ev_info,1),
            fprintf('*************** ERROR ******************\n');
            fprintf('add_ev_info.m: Your file %s has the same ',event_infofile);
            fprintf('event on multiple rows.\n');
            fprintf('All the information for a single event should ');
            fprintf('be on one row.\n');
            fprintf(['Only the topmost row for each event will be' ...
                ' imported.\n']);
            fprintf('Additional rows for an event will be ignored.\n');
            file_ev_info=file_ev_info(uni_id,:);
        end
        
        %%%Add event info to existing epoch information
        n_ev=length(blf_ev_num);
        
        %If an event isn't listed in this file, it will have NaN values
        new_info=zeros(n_ev,size(file_ev_info,2)-1)*NaN;
        ct=0;
        for dg=file_ev_info(:,1)',
            ct=ct+1;
            id=find(blf_ev_num==dg);
            new_info(id,:)=file_ev_info(ct,2:end); %first col ignored
            %because it's just the
            %event number
        end
        
        %return all header names except for the first column
        clear info_names;
        for dg=1:(length(ev_col_hdrs)-1),
            info_names{dg}=ev_col_hdrs{dg+1};
        end
    end
    fclose(ev_fid);
end

