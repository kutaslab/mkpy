function [loc_struct] = get_loc(hinfo,hdr,channel_info)

% location and channels information from hdr
loc = hdr.apparatus.sensors;
stream = hdr.apparatus.streams;
sensor_names = fieldnames(loc);
stream_names = fieldnames(stream);

% channel info from Data
% sub=1;block=1; % retreive chn info from 1st sub/block. assuming this info is constant across block and subjects
% d2read = [char(39),sprintf(hinfo.Groups(sub).Name),'/',sprintf(hinfo.Groups(sub).Datasets(block).Name),char(39)];
% column_info = fieldnames(h5read(filename,eval(d2read)));
% channel_info = column_info(7:end);

xyz=[];ref=[];
for i=1:length(channel_info)
    osensor = sprintf('%s%s','loc.',channel_info{i});
    nsensor = sprintf('%s%s','loc_cell.',channel_info{i});
    ostream = sprintf('%s%s','stream.',channel_info{i});
    if sum(strcmpi(channel_info{i},stream_names))
        idx = find(strcmpi(channel_info{i},stream_names));
        ostream = sprintf('%s%s','stream.',stream_names{idx});
        ref = [ref ;struct2cell(eval(ostream))'];
        if sum(strcmp(channel_info{i},sensor_names))
            a = eval(osensor);
            loc_idx = find(strcmp(fieldnames(a)',{'x','y','z'}));
            if sum(loc_idx)>0,
                txyz = struct2cell(eval(osensor))';
                xyz = [xyz;txyz(loc_idx)];
            else
                xyz = [xyz ; num2cell(nan(1,3))];
            end
        else
            xyz = [xyz ; num2cell(nan(1,3))];
        end
    else
            xyz = [xyz ; num2cell(nan(1,3))];        
    end
end;
ref = ref(:,2);
l_xyz = [cell(length(xyz),2) channel_info cell(length(xyz),3) xyz ref repmat({'EEG'},length(xyz),1), cell(length(xyz),1)];

% note that x and y swap for eeglab default
loc_table = cell2table(l_xyz,'VariableNames',{'theta','radius','labels','sph_theta','sph_phi','sph_radius','Y','X','Z','ref','type','urchan'});
loc_struct = table2struct(loc_table);
    