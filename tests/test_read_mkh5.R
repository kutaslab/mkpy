library(methods)
library(jsonlite)
library(rhdf5)  # from bioconductor.org
library(yaml)
library(iotools)

## test hdf5 data file loading
test_read_h5 <- function(h5_f=NULL){
    if (is.null(h5_f)){
        h5_f <- paste('/home/turbach/TPU_Projects/mkpy/mkpy/tests/data/for_R.h5', sep='')
    }
    print(paste('File:', h5_f))

    h5tree = h5ls(h5_f) # tabulate the tree
    print('ok')
    h5f <- H5Fopen(h5_f)
    # print(h5tree)

    # subset the datasets from the tree (skip groups)
    h5_paths = h5tree[which(h5tree$otype == 'H5I_DATASET'),]

    # walk the tree reading the data 
    for (d in c(1:nrow(h5_paths))){
        full_name = sprintf('%s/%s',
                            h5_paths$group[d],
                            h5_paths$name[d])

        full_name = sub('^/','',full_name) # strip root /
        # access the data via & *pointer* to rather $ copy
        # x = (h5f&'S01/dblock_0')[]
        # x = (h5f&full_name)[]
        x = (h5f&full_name)[]

        cat(full_name, '\n')
        cat('  head: ', sprintf('%5.8f', head(x,3)), '\n')
        cat('  tail: ', sprintf('%5.8f', tail(x,3)), '\n')
        cat('  mean: ', mean(x), 'sd:', sd(x), 'sum', sum(x), '\n')


        # Attributes 
        # > help(H5Aread)
        att_id = H5Aopen(h5f&full_name, 'json_attrs')
        json_attrs= H5Aread(att_id) # as json string
        attrs = fromJSON(json_attrs) # as R data structures

        mood = data.frame(attrs$runsheet$mood_induction_table$rows)
        names(mood) = attrs$runsheet$mood_induction_table$columns

    }
    # h5f.Close()
    H5Fclose(h5f) # works intermittently on the cluster ...

    H5close()
    cat('OK\n')
}


load_yhdr <- function(yhdr_f=NULL){
    if (is.null(yhdr_f)){
        yhdr_f<- paste('/home/turbach/TPU_Projects/mkpy/mkpy/tests/data/test2.yhdr', sep='')
    }
    print(paste('File:', yhdr_f))

    # con=file(yhdr_f,open="r")
    # yaml_chars=readLines(con)
    # str(yaml_chars)
    # docs = str_split(yaml_chars, '-{3,}')
    hdr_str = readLines(yhdr_f)
    #yaml_chars = readAsRaw(yhdr_f)
    #print(length(yaml_chars))
    #print(length(str_sub(yaml_chars, ' ')))
    #stop()
    hdr = list()
    doc_str = ''
    for (i in seq(length(hdr_str))){
        l = hdr_str[i]
        if (str_detect(l, '-{3,}') | l == length(hdr_str)){
            if (length(doc_str) > 0){
                doc_str = sprintf("%s\n%s","---",doc_str)
                print('decoding doc')
                ## print(doc_str)
                ydoc = yaml.load(doc_str)
                show(ydoc$name)
                 #hdr$docname
                 doc_str= '' # reset
             }
         }
         doc_str = sprintf("%s\n%s", doc_str, l)
    }
    show(names(hdr))
    # mood = data.frame(hdr$runsheet$mood_induction_table$rows)
    # names(mood) = hdr$runsheet$mood_induction_table$columns
    # show(mood)

}
