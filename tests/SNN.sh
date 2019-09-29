#!/bin/sh
# pass in the value of the cal pulse: 1, 5, 10, or 20 
cal=$1
spfx=`printf "S%02d" ${cal}`

echo "#------------------------------------------------------------"
echo "# ERP pipeline: ${spfx}"
echo "#------------------------------------------------------------"

# clean up previous
for suffix in blf cnts; do 
    rm -f data/${spfx}.${suffix}
    rm -f data/${spfx}.x.${suffix}
done

for suffix in avg out nrm nrf; do 
    rm -f data/${spfx}.${suffix}
    rm -f data/${spfx}.x.${suffix}
done

# begin
presamp=100
cprecis=1
arf=$spfx.x.arf

# make a read/writeable working copy of the .log for decoration with avg -x
cp  data/$spfx.log data/$spfx.x.log
chmod 660 data/$spfx.x.log

# generate blf
cdbl data/SNN.bdf data/$spfx.x.log data/$spfx.x.blf 250 > data/$spfx.x.cnts

# generate avg with and without rejections
echo "data/$spfx.crw data/$spfx.x.log data/$spfx.x.blf" | avg $presamp data/$spfx.avg -x -c $cprecis -o data/$spfx.out
#    echo "data/$spfx.crw data/$spfx.x.log data/$spfx.x.blf" | avg $presamp data/$spfx.x.avg -x -a data/$arf -c $cprecis -o data/$spfx.x.out

# note cal param
normerp data/$spfx.avg data/$spfx.nrm -a 3 -n -50 100 ${cal} 1 1000

echo "cdbl counts"
cat data/${spfx}.x.cnts
echo "avg bin counts"
cat data/${spfx}.out
#    normerp data/$spfx.x.avg data/$spfx.x.nrm -a 3 -n -50 100 ${cal} 1 1000

# generate bimastoid referenced + VEOG channel data file
# dmanip data/EOG.A1A2.mnp data/$spfx.x.nrf -g 3 data/$spfx.x.nrm

# merp the avg and nrm
cd data
rm -f ${spfx}.mrp.dat
merp ${spfx}.mcf > ${spfx}.mrp.dat

#rm -f ${spfx}.x.mrp.dat
#merp ${spfx}.x.mcf > ${spfx}.x.mrp.dat
cd ..

# done

