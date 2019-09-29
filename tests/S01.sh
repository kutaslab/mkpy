#!/bin/sh

spfx=lm01   
subno=lm01  
stimlist=A  

# clean up previous
for suffix in blf cnts; do 
    rm -f data/${spfx}.${suffix}
done

for suffix in avg out nrm nrf; do 
    rm -f data/${spfx}.${suffix}
done

# begin
presamp=500
cprecis=2
arf=$subno.c2.arf

# make a read/writeable working copy of the .log for decoration with avg -x
cp  data/$subno.log ../Data/$subno.x.log
chmod 660 ../Data/$subno.x.log

# generate blf
cdbl ../Data/logmetList${stimlist}.bdf ../Data/$subno.x.log ../Data/$spfx.blf 250 > ../Data/$subno.cnts

# generate avg 
echo "../Data/$subno.crw ../Data/$subno.x.log ../Data/$spfx.blf" | avg $presamp ../Avg/$spfx.avg -x -a ../Arf/$arf -c $cprecis -o ../Avg/$spfx.out

# generate uV data file
normerp ../Avg/$spfx.avg ../Avg/$spfx.nrm -a 5 -n -50 100 10 1 1000

# generate bimastoid referenced + VEOG channel data file
dmanip ../Mnp/tpu_EOG.A1A2.mnp ../Avg/$spfx.nrf -g 47 ../Avg/$spfx.nrm
