from scipy.spatial import KDTree
import logging
import numpy as np
import xarray as xr
from datetime import datetime, timedelta

def add_new_SEPA_nb(sepafile, farm_data):
    '''
    Add information from new SEPA GSID to modelled farms
    '''
    with open(sepafile) as ff:
       ff.readline()
       for line in ff:
           line=line.strip().split(',')
           try:
               farm_data[line[0]]['GSID']=line[1]
           except:
               logger.debug(f'{line[0]} not found in farmdata')
    return farm_data

def read_farm_data(farmfile, lice_data):
    data={}
    logger.info('########## READING BIOMASS DATA #######')
    with open(farmfile) as f:
        head=f.readline().strip().split(',')[21:]
        times = np.array([np.datetime64(datetime.strptime(h,'%m/%d/%Y')) for h in head])
        f.readline()
        id=0
        for line in f:   
            line=line.strip().split(',')
            data[line[0]]= {'additional location':line[1],
                            'Name MS': line[2],
                            'Site ID SEPA': line[3].strip(),
                            'Site ID Scot env':str(line[4]).strip(),
                            'lat':float(line[6]),'lon':float(line[7]),
                            'Prod year':line[9],
                            'licensed peak biomass':line[10],
                            'operator':line[13],
                            'production cycle':line[14],
                            'production in 3 years 2021': line[18],
                            'ID':id,
                            #'odd':random() < 0.5,
                            }
            id+=1
            ref=0
            biom=np.zeros(len(line[21:]))
            for i in range(len(line[21:])):
                try:
                    b = float(line[21+i])
                    biom[i]=b
                    if b>ref:
                        ref=b
                except:
                    biom[i]=np.nan
            data[line[0]]['reference biomass']= ref            
            data[line[0]]['biomasses']=biom
            data[line[0]]['lice data'], data[line[0]]['mean lice']=add_lice_data(line[4], lice_data)       
            if ref==0:
                id -=1 
                del data[line[0]]
            #ref_biom[id]=ref
    logger.info('########## BIOMASS DATA READ ###########')
    Ids=np.array([data[farm]['Site ID Scot env'] for farm in data.keys()])
    tree = None #mk_kde_tree(data)
    return data, times, tree , Ids

def mk_kde_tree(data):
    logger.info('########## Making KDe Tree   ###########')
    Xs= np.array([data[farm]['lon'] for farm in data.keys()])
    Ys= np.array([data[farm]['lat'] for farm in data.keys()])
    
    tree = KDTree(np.vstack((Xs,Ys)).T)
    logger.debug(f'Kde tree :       {tree}')
    logger.info('########## Tree Made ############')
    return tree

def read_future_farms(filename):
    new_farm=np.genfromtxt(filename,
                           names=True,
                           delimiter='\t', 
                           dtype=['U10','U30','i8','f8','f8'])
    return new_farm

def add_lice_data(SEPA_ID, lice_data):
    arr= np.zeros(261)
    arr[:]=np.nan
    av=np.nan
    for licence in lice_data.keys():
        if licence==SEPA_ID:
            arr= lice_data[licence].values
            av = lice_data[licence].values.mean()
    return arr, av
    
def prepare_zarr():
    # zoom 10 = 38.218 m so if zoom > 9 50m zarr then image is max 512 px
    # should we fix the width to 1024? zarr needs 256 chunks to go faster probably
    # first zoom 5.5 so compute for zoom 5 to 9 (5 zarrs) 50(9) - 100 (8) - 200 (7) - 400(6) - 800 (5)
    ds=xr.open_zarr('westcoast_map_trim.zarr/')#.chunk(chunks={'x':256,'y':256})
    for (res, zoom) in zip([50,100,200,400,800],[9,8,7,6,5]):
        ds= ds.coarsen(x=2,boundary='pad').mean().coarsen(y=2,boundary='pad').mean()#.chunk(chunks={'x':256,'y':256})
        ds.to_zarr(f'map_{res}m.zarr')#, safe_chunks=False)
    return
    
def search_lice_data(start,end, ident, farm, l_data, fdata, lice_time):
    '''
    Search if there are data for the farm at the chosen date.
    Check it is not null
    return may data if available
    if not, try to return the average lice value for the farm.
    '''
    logger.debug(f'searching lice data for {ident}')
    t_filter= np.where(np.logical_and(lice_time> start, lice_time< end))[0]
    # logger.debug(f'Data for {ident} are:    {l_data}')
    may_data= np.array(l_data)[t_filter].mean()
    if not np.isnan(may_data):
            if may_data>0:
                logger.info(f'found may data for {ident}')
                return may_data
    else:
            if np.isnan(fdata['mean lice']) is False:
                logger.info(f'Used average for {ident}')
                return fdata['mean lice']

    
    

#if 'All_names' not in globals():
#    logger.info('loading dataset')
#    master='curr_800m.zarr'
#    super_ds=open_zarr(rootdir+master)
#    All_names=np.array(list(super_ds.keys()))
#    ## remove border effects
#    #super_ds= super_ds.where(super_ds.x<-509600)
#    future_farms=read_future_farms(rootdir+'future_farms.txt')


# ref_biom=np.zeros(len(All_names))
    
#if 'lice_data' not in globals():
#    liceStore='consolidated_sealice_data_2017-2021.zarr'
#    lice_data=open_zarr(rootdir+liceStore)
#    ### mess in raw data
#    id_c=250
#    typos =['Fs0860', 'Fs1018', 'Fs1024'] #, 'FS1287 '
#    correct=['FS0860', 'FS1018', 'FS1024']
#    for mess, ok in zip(typos, correct):
#        lice_data[ok].values[id_c]=lice_data[mess].values[id_c]
#        lice_data=lice_data.drop(mess)
    
    
#if 'farm_data' not in globals():
#    csvfile='biomasses.csv'
#    farm_data, times, tree, Ids =read_farm_data(rootdir+csvfile)
#    logger.info('Farm loaded')
#    sepacsv= 'SEPA_GSID.csv'
#    farm_data=add_new_SEPA_nb(rootdir+sepacsv)
    
    
############# initialise variables before first callback to use context #############
def initii():
	template = template_theme1 
	cmp= cmp1
	carto_style= carto_style1
	activated_farms= np.ones(len(All_names), dtype='bool')
	Coeff=np.ones(len(All_names)) 
	biomass_factor=np.ones(len(All_names))
	lice_factor=np.ones(len(All_names))/2
	idx, biomass_factor, lice_factor, ref_biom=fetch_biomass(activated_farms, 
                                                     biomass_factor, lice_factor, 2021)
	name_list=np.array(list(farm_data.keys()))[idx] 
	current_biomass=[farm_data[farm]['reference biomass']*
                                           biomass_factor[farm_data[farm]['ID']]
                                           for farm in name_list]
	Coeff=30/16.9*biomass_factor[idx]*lice_factor[idx]
	alllice=(Coeff*ref_biom[idx]).sum()*4.5*1000


logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('sealice_logger')
logger.setLevel(logging.DEBUG)
