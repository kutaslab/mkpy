function [new_info, info_names]=add_sbjct_info(sbjct_infofile,sbjct_id)
% add_code_info() - Reads information about a subject (e.g., their age,
%                   working memory span, etc...) from a text file and stores
%                   the information as a vector that can be easily added to
%                   existing epoch information in the function crw2set.m.
%
%
% Usage:
%  >> [new_info, info_names]=add_code_info(sbjct_infofile,sbjct_id)
%
% Required Global Variable:
%   VERBLEVEL         = matlabMK level of verbosity (i.e., tells functions
%                        how much to report about what they're doing during
%                        runtime)
%
% Inputs:
%   sbjct_infofile     = the name of a space or tab delimited text file
%                        containing numeric information about subjects
%                        (e.g., age, working memory span).  The first
%                        row of the file is a header line with a
%                        one word description of each column in the
%                        file. Each row below the headerline
%                        corresponds to a different subject.  The
%                        first column of the file provides an ID number/code
%                        name for each participant.  Additional columns
%                        specify numeric subject information.
%
%   sbjct_id          = a string that identifies the subject.
%                       The value of 'sbjct_id' must match one of the cells
%                       in the first column of 'sbjct_infofile'.
%
% Outputs:
%   new_info          = a vector of new event information that can
%                        be appended to the existing blf info
%                        matrix
%   info_names        = a cell array of strings containing the
%                        header information for each column of
%                        sbjct_infofile. The first column of
%                        sbjct_infofile is ignored since it should just
%                        contain subject IDs.
%
%
% Additional Notes:
%
% Don't use parenthesis in column header names.  MATLAB interprets
% the name as a function call.
%
% Use NaN to fill cells for subjects that don't have a value for a
% particular column
%
% Author:
% David Groppe
% Kutaslab, 10/2009

global VERBLEVEL

new_info=[];
info_names=[];

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% LOAD INFORMATION ABOUT EACH SUBJECT FROM A TEXT FILE
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
VerbReport(sprintf('Getting information about subject from %s', ...
		   sbjct_infofile), 1, VERBLEVEL);  
[sub_fid, message]=fopen(sbjct_infofile,'r');
if (sub_fid==-1)
    error('Cannot open file %s.  According to fopen: %s.\n',sbjct_infofile,message);
else
  %read column headers
  txtline = fgetl(sub_fid);
  if (txtline==-1)
    error('File %s is empty.\n',sbjct_infofile);
  else
    %Read column header
    clear sub_col_hdrs;
    [sub_col_hdrs{1}, rmndr]=strtok(txtline);
    col_ct=1;
    fprintf('Subject ID column is: %s\n',sub_col_hdrs{1});
    while ~isempty(rmndr)
      col_ct=col_ct+1;
      [sub_col_hdrs{col_ct}, rmndr]=strtok(rmndr);
      fprintf('Column %d is: %s\n',col_ct,sub_col_hdrs{col_ct});
    end
        
    %Read subject information
    row_ct=1;
    while ~feof(sub_fid)
        txtline = fgetl(sub_fid);
        col_ct=1;
        while ~isempty(txtline)
            [neo_val, txtline]=strtok(txtline);
            if col_ct==1,
                crnt_sub_id=neo_val;
            else
                file_sub_info(row_ct,col_ct-1)=str2double(neo_val); %events that
                %do not have a value for that column
                %should be represented as NaN
                if isempty(str2num(neo_val))
                    watchit(sprintf(['Subject info file %s appears to have a non-numeric entry at Subject %s, column %s.\n', ...
                        'When using crw2set only numeric values are permitted.  Use sbjct_info2set.m for non-numeric values.'], ...
                        sbjct_infofile,crnt_sub_id,sub_col_hdrs{col_ct}));
                end
            end
            col_ct=col_ct+1;
        end
        if strcmpi(crnt_sub_id,sbjct_id)
            if isempty(new_info),
                new_info=file_sub_info(row_ct,:);
                %keep searching just in case the subject was entered more
                %than once in the info file
            else
                error('File %s has multiple entries for subject %s.  Only one row per subject is allowed.\n',sbjct_infofile,sbjct_id);
            end
        end
        row_ct=row_ct+1;
    end
    if isempty(new_info),
       error('Could not find subject %s in file %s.  A cell in the first column of %s should contain %s.\n',sbjct_id, ...
           sbjct_infofile,sbjct_infofile,sbjct_id);
    end
    
    %return all header names except for the first column
    info_names=cell(1,length(sub_col_hdrs)-1);
    for dg=1:(length(sub_col_hdrs)-1),
      info_names{dg}=sub_col_hdrs{dg+1};
    end
  end
  fclose(sub_fid);
end

