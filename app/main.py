# This file is part of sealice visualisation tools.
#
# This app is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3
#
# The app is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details., see
# <https://www.gnu.org/licenses/>.
#
# Copyright 2022, Julien Moreau, Plastic@Bay CIC


# import gcsfs
from  xarray import open_zarr
#from rasterio.enums import Resampling
import rioxarray
import json, logging, orjson
#from google.cloud import storage
import numpy as np

from pyproj import Proj
# from random import random
import datashader as DS
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from colorcet import fire, bmy
from datashader import transfer_functions as tf
from datetime import datetime, timedelta
from os import path, environ
import dash
from dash import dcc as dcc
from dash.exceptions import PreventUpdate
from dash import html as html
from dash import Dash
from dash.dependencies import Input, Output, State, MATCH, ALL
# from dash_extensions.enrich import Output, Input, html, State, MATCH, ALL, DashProxy, LogTransform, DashLogger, dcc # FileSystemStore #ServersideOutput, ServersideOutputTransform, 
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template
import dash_mantine_components as dmc

import dash_daq as daq

from flask_caching import Cache
# from dash.exceptions import PreventUpdate
from celery import Celery

from layout import *
from preprocess import *

class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return (str(obj))
        else:
            return json.JSONEncoder.default(self, obj)
            

class DashLoggerHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)
        self.queue = []

    def emit(self, record):
        msg = self.format(record)
        self.queue.append(msg)

def get_coordinates(arr):
    logger.debug('compute corner coordinates of filtered dataset')
    coordinates=np.zeros((4,2))
    coordinates[0]=p(arr.x.values[0],arr.y.values[0], inverse=True)
    coordinates[1]=p(arr.x.values[-1],arr.y.values[0], inverse=True)
    coordinates[2]=p(arr.x.values[-1],arr.y.values[-1], inverse=True)
    coordinates[3]=p(arr.x.values[0],arr.y.values[-1], inverse=True)
    return coordinates[::-1]

def crop_ds(ds, viewdata):
    return ds.where((ds.x<viewdata['xmax'] ) &
                           (ds.x>viewdata['xmin'] ) &
                           (ds.y>viewdata['ymin'] ) &
                           (ds.y<viewdata['ymax'] ), drop=True)
                           
    
def calculate_edge(coordinates):
    #'mapbox._derived': 
    #{'coordinates': 
    #[[-10.222445323498363, 58.30071109904159], 
    #[-2.1601633454028786, 58.30071109904159], 
    #[-2.1601633454028786, 55.988518444614954], 
    #[-10.222445323498363, 55.988518444614954]
    box=np.zeros_like(coordinates)
    
    for i in range(len(coordinates)):
       box[i]=p(coordinates[i,0],coordinates[i,1])
    corners={'xmin':box[:,0].min()-800,
             'xmax':box[:,0].max()+800,
             'ymin':box[:,1].min()-800,
             'ymax':box[:,1].max()+800
             }
    return corners

def mk_img(ds, span, cmp):
    '''
    Create an image to project on mabpox
    '''
    logger.info('making raster...')  
    arr= ds.to_stacked_array('v', ['y', 'x']).sum(dim='v')
    logger.info('data stacked')
    polyg= [{"type":"Polygon",
              "coordinates":[[
                [-890556, 7719350],
                [-829330, 7618370],
                [-857160, 7588335],
                [-912820, 7688916],
                [-890556, 7719350]
              ]]
            }]
    arr= arr.rio.write_crs(3857, inplace=True).rio.clip(polyg, invert=True, crs=3857)
    logger.info('data cropped')
    #sel1=arr.where((arr>=0.001 & arr<0.01))
    #sel2=arr.where((arr>=0.01  & arr<0.03))
    #sel3=arr.where((arr>=0.03  & arr>0.1 ))
    #sel4=arr.where((arr>=0.1   & arr>0.3 ))
    #sel5=arr.where((arr>=0.3   & arr>0.75))
    #bins=[0.001,0.01,0.03,0.1,0.3,0.75]
    #temp=tf.shade(arr.groupby_bins(bins).groups).to_pil()
    temp= tf.shade(arr.where(arr>0), cmap=cmp, how='linear', span=span).to_pil()
    return temp

def select_zoom(zoom):
    '''
    select the zarr resolution according to the zoom for preselection 
    trying to match https://docs.mapbox.com/help/glossary/zoom-level/
    '''
    if zoom <6:
        r=800
    elif zoom>=9.1:
        r= 50
    elif 6<=zoom<7.1:
        r=400
    elif 7.1<=zoom<8.1:
        r=200
    elif 8.1<zoom<=9.1:
        r=100
    return r

def query_tree():
   seek= tree.query(np.array([farm_data[farm]['lon'], farm_data[farm]['lat']]).T, n)[1]
   for i in range(n):
                    remote_data= search_lice_data(start,end, Ids[i], farm, lice_data, farm_data)
                    if remote_data is not None :
                        return remote_data
                        
    
def fetch_biomass(farm_data, lice_data, activated_farms, biomass_factor, lice_factor, times, ref_biom, Ids, lice_time, flag, year=2018):
    '''
    Identify the biomass data for the month of may of the chosen year
    scale the data according to data
    remove farm with no data for the month
    if flag is true (toggle is on) try to populate the lice density for each farm
    '''
    n= 50 #nb of nearest farms
    start, end = np.datetime64(datetime(year=year, month=4,day=30),'D'), np.datetime64(datetime(year=year, month=6,day=1),'D')
    filters=np.where(np.logical_and(times> start, times< end))[0]
    filtered=times[filters]
    for farm in farm_data.keys():       
        extract=np.array(farm_data[farm]['biomasses'])[filters]
        extract=np.nanmean(extract[extract!=0])
        if np.isnan(extract):
            activated_farms[farm_data[farm]['ID']]= False
        else:
            biomass_factor[farm_data[farm]['ID']]=extract/farm_data[farm]['max biomass']
            ref_biom[farm_data[farm]['ID']]=farm_data[farm]['max biomass']
            if flag:
                ident=farm_data[farm]['Site ID Scot env']
                if len(ident)>0:
                    local_data=search_lice_data(start,end, ident, 
                                            farm, lice_data['data_vars'][ident]['data'], 
                                            farm_data[farm], lice_time)
                    if local_data is not None :
                        lice_factor[farm_data[farm]['ID']]=local_data
                    else:
                       logger.debug(f'No lice data for farm {farm} during May {year}')
                       lice_factor[farm_data[farm]['ID']]=0.5                   
                else:
                    logger.debug(f'No ID for farm {farm}')
                    lice_factor[farm_data[farm]['ID']]=0.5
                
    return activated_farms, biomass_factor, lice_factor, ref_biom      

def render(fig, ds, span, theme, name_list):
     logger.info('Rendering')
     coordinates=get_coordinates(ds)
     logger.debug(f'Selected farms for the map:   {name_list}')
     logger.debug(f'coordinates:     {coordinates}')
     fig['layout']['mapbox']['layers']=[{
                                        "below": 'traces',
                                        "sourcetype": "image",
                                        "source": mk_img(ds, span, theme['cmp']),
                                        "coordinates": coordinates
                                    },]
     logger.info('raster loaded')
     return fig

#### SET LOGGER #####
logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('sealice_logger')
logger.setLevel(logging.DEBUG)
autocl=2000 #time to close notification
dashLoggerHandler = DashLoggerHandler()
logger.addHandler(dashLoggerHandler)

############# VARIABLES ##########################33
 # value extent
resolution=[50,100,200,400,800]
zooms=[9,8,7,6,5]
# start, end = "2018-05-01", "2018-05-31"
marks_biomass={
        0.1:'10%',
        0.25:'25%',
        0.5:'50%',
        0.75:'75%',
        1:'100%',
        1.25:'125%',
        1.5:'150%',
        1.75:'175%',
        2:'200%',
    }
marks_lice={
        0.25:'0.25',
        0.5:'0.5',
        0.75:'0.75',
        1:'1',
        2:'2',
        3:'3',
        4:'4',
        5:'5',
        6:'6',
        7:'7',
        8:'8'
    }
    
p=Proj("epsg:3857", preserve_units=False)


##################### FETCH DATA ###################
# test local vs host
if path.exists('/mnt/nfs/home/data/'):
    rootdir='/mnt/nfs/home/data/'
else:
    rootdir='/media/julien/NuDrive/Consulting/The NW-Edge/Oceano/Westcoast/super_app/data/'


    
template_theme1 = "slate"
template_theme2 = "sandstone"
load_figure_template([template_theme1,template_theme2])
url_theme1=dbc.themes.SLATE
url_theme2=dbc.themes.SANDSTONE
cmp1= fire
cmp2= bmy
carto_style1="carto-darkmatter"
carto_style2="carto-positron"
dbc_css = (
    "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.1/dbc.min.css"
)

# Cache config
cacheconfig={'CACHE_TYPE': 'RedisCache',
             'CACHE_REDIS_HOST': environ['REDIS_URL']
    }
#celery_app = Celery(__name__, broker=environ['REDIS_URL'], backend=environ['REDIS_URL'])
#background_callback_manager = dash.CeleryManager(celery_app)

######### APP DEFINITION ############
#my_backend = FileSystemStore(cache_dir="/tmp")
app = Dash(__name__,
                external_stylesheets=[url_theme1],#, dbc_css
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1, maximum-scale=1.2, minimum-scale=0.5"}],
                #transforms=[] #LogTransform(), ServersideOutputTransform(backend=my_backend)
                )
server=app.server
#### need to make a way to swap between localhost and 
cache = Cache(app.server, config=cacheconfig)
timeout = 300

@server.route('/_ah/warmup')
def warmup():
    """Warm up an instance of the app."""
    return "it is warm"
    # Handle your warmup logic here, e.g. set up a database connection pool


app.title="Heatmap Dashboard"
app.layout = dbc.Container([
    html.Div([    #Store
        dcc.Store(id='init', storage_type='session'),
        dcc.Store(id='bubbles', storage_type='session'),
        dcc.Store(id='lice_store', storage_type='session'),
        dcc.Store(id='view_store', storage_type='session'),
        dcc.Store(id='theme_store', storage_type='session'),
        dcc.Store(id='planned_store', storage_type='session'),
        dcc.Store(id='fig_store', storage_type='session'),
        dcc.Store(id='selection_store',storage_type='session'),
        dcc.Store(id='tab2_store',storage_type='session'),
        ]
        ),
    html.Div(id='modal_div'),
    dbc.Card([
        dbc.CardHeader(main_header()),
        dbc.CardBody([
            dbc.Tabs(id='all_tabs',
                    children= [
                        dbc.Tab(tab1_layout(),label='Interactive map',tab_id='tab-main',),
                        dbc.Tab(tab2_layout(),label='Selected area inspection', tab_id='tab-area'),
                        dbc.Tab(tab3_layout(),label='Farm data inspection',tab_id='tab-graph',),
                        dbc.Tab(tab4_layout(), label='Documentation', tab_id='tab-doc'),
                    ])
             ]),
        dbc.CardFooter([main_footer()])
        ])    
     ], fluid=True, className='dbc')

# there is a chance that this is shared between users...
@cache.memoize()
def global_store(r):
    pathtods=f'curr_{r}m.zarr'
    pathtofut=f'planned_{r}m.zarr'
    logger.info(f'using global store {pathtods}')
    super_ds=open_zarr(rootdir+pathtods).drop('North Kilbrannan')
    super_ds=super_ds.where(super_ds.x<-509945) # remove the border
    logger.debug(f'zarr chunks:   {super_ds.chunks}')
    planned_ds= open_zarr(rootdir+pathtofut)
    return super_ds, planned_ds

@cache.memoize    
@app.callback(
     Output('init', 'data'),
     Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def initialise_var(toggle):
    logger.info('Preparing dataset')
    variables={}
    master='curr_800m.zarr'
    super_ds=open_zarr(rootdir+master).drop('North Kilbrannan')
    variables['All_names']=np.array(list(super_ds.keys()))
    variables['future_farms']=read_future_farms(rootdir+'farm_data/future_farms.txt')
    variables['ref_biom']=np.zeros(len(variables['All_names']))
    liceStore='farm_data/consolidated_sealice_data_2017-2021.zarr'
    lice_data=open_zarr(rootdir+liceStore)
    ### Correct typos in the raw data
    id_c=250
    typos =['Fs0860', 'Fs1018', 'Fs1024'] 
    correct=['FS0860', 'FS1018', 'FS1024']
    for mess, ok in zip(typos, correct):
        lice_data[ok].values[id_c]=lice_data[mess].values[id_c]
        lice_data=lice_data.drop(mess)
    variables['lice_data']=lice_data.to_dict()
    variables['lice time']=variables['lice_data']['coords']['time']['data']
    csvfile='farm_data/biomasses_to_03-2023.csv'
    variables['farm_data'], variables['times'], _ , variables['Ids'] =read_farm_data(rootdir+csvfile, lice_data, super_ds.keys())
    logger.info('Farm loaded')
    sepacsv= 'farm_data/SEPA_GSID.csv'
    variables['farm_data']=add_new_SEPA_nb(rootdir+sepacsv, variables['farm_data'])
    logger.info('Variables loaded')
    return json.dumps(variables, cls= JsonEncoder) 
#orjson.dumps(variables, option= orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY)

@app.callback(
    Output('theme_store', 'data'),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def record_theme(toggle):
     ### toggle themes    
    theme={}
    theme['template'] = template_theme1 if toggle else template_theme2
    theme['cmp']= cmp1 if toggle else cmp2
    theme['carto_style']= carto_style1 if toggle else carto_style2
    return json.dumps(theme)

@app.callback(
    Output('egg_toggle_output','children'),
    Input('egg_toggle','on'),
)
def toggle_egg_models(eggs):
    if eggs:
        return 'Stien et al. (2005)'
    else:
        return 'Rittenhouse et al. (2016)'

@app.callback(
    Output('lice_store','data'),
    [Input('lice_knob','value'),
    Input('egg_toggle','on'),
    Input('lice_meas_toggle','on'),
    Input('init','data'),],
    )
def compute_lice_data(liceC, egg, meas, init):
    logger.info('scaling lice')
    logger.debug(f'egg is {egg}')
    variables=json.loads(init)
    # modify egg model from Rittenhouse (16.9) to Stein (30)
    if egg:
        c_lice=30/16.9
    else:
        c_lice=1
    lice_factor=np.ones(len(variables['All_names']))/2
    if not meas:
        liceC *=2
        if liceC==0:
            liceC=0.00001
        lice_factor*=liceC
    lice_factor *= c_lice
    return [{'lice factor': lice_factor, 
                       'lice knob': liceC, 
                       'egg factor': c_lice}]
    
@app.callback(
    Output('view_store','data'),
    Output('trigger','children'),
    Input('heatmap', 'relayoutData'),
    )
def store_viewport(relay):
    logger.debug('Storing viewport data')
    logger.debug(f'relay: {relay}')
    default_view=[[-16., 60.], 
            [5., 60.], 
            [5., 53.], 
            [-16., 53.]]
    if relay is not None:
        if 'mapbox.zoom' in relay.keys():
            zoom=relay['mapbox.zoom']
        else:
            zoom=5.
        if 'mapbox._derived' in relay.keys():
            bbox=relay['mapbox._derived']['coordinates']
        else:
            bbox=default_view
    else:
        zoom=5.
        bbox=default_view
    corners=calculate_edge(np.array(bbox))
    corners['zoom']=zoom
    res=select_zoom(zoom)

    return json.dumps(corners, cls= JsonEncoder), f'Render density map at {res}m resolution'
    
@app.callback(
    Output('selection_store','data'),
    Input('heatmap', 'selectedData'),
    ) 
def store_selections(selection):
    logger.debug('Storing selection data')
    #logger.debug(selection)
    polygon= [
              {'type': 'Polygon',
               'coordinates': []
               }]
    if selection is not None:
        if 'lassoPoints' in selection.keys():
            polygon[0]['coordinates']= [selection['lassoPoints']['mapbox']]
            logger.debug(f'lasso: {polygon}')
        if 'range' in selection.keys():
            corners= selection['range']['mapbox'] 
            #corners [[-5.830548160160845, 56.100192972898526], [-4.578531927385427, 55.50624123351233]]}}
            polygon[0]['coordinates']= [[corners[0], 
                      [corners[0][0], corners[1][1]],
                      corners[1], 
                      [corners[1][0],corners[0][1]],
                      corners[0]]]
            logger.debug(f'rectangle: {polygon}')        
    return json.dumps(polygon, cls= JsonEncoder)

@app.callback(
    Output('bubbles','data'),
    [
    Input('year_slider','value'),
    Input('biomass_knob','value'),
    Input('lice_store','modified_timestamp'), 
    Input('init', 'data'), 
    Input('lice_store','data'),  
    ],
    [   
    State('lice_meas_toggle','on')
    ],
)
def mk_bubbles(year, biomC,lice_tst, init, liceData, meas):
    liceData=liceData[0]
    variables=json.loads(init)
    activated_farms= np.ones(len(variables['All_names']), dtype='bool')
    Coeff=np.ones(len(variables['All_names'])) 
    biomass_factor=np.ones(len(variables['All_names']))
    lice_factor=np.array(liceData['lice factor'])
    if biomC ==0:
        biomC=0.00001
    biomC /=100
    logger.info('preparing lice factor')
    idx, biomass_factor, lice_factor, ref_biom=fetch_biomass(variables['farm_data'], variables['lice_data'], 
                                                     activated_farms, biomass_factor, lice_factor, 
                                                     np.array(variables['times'],dtype='datetime64[D]'), 
                                                     np.array(variables['ref_biom']), variables['Ids'], 
                                                     np.array(variables['lice time'], dtype= "datetime64[D]"),
                                                     meas, year)
    name_list=np.array(list(variables['farm_data'].keys()))[idx]    
    ##### update discs farms
    current_biomass=[variables['farm_data'][farm]['licensed peak biomass']*
                                    biomass_factor[variables['farm_data'][farm]['ID']] *biomC
                                    for farm in name_list]
        # set global factor biomass x individual farm biom x individual lice x egg model
    logger.debug(f'idx:      {type(idx)}')
    logger.debug(f'biomass factor:      {type(biomass_factor)}')
    logger.debug(f'lice factors:      {type(lice_factor)}')
    Coeff=biomC*biomass_factor[idx]*lice_factor[idx]
    alllice=(Coeff*ref_biom[idx]).sum()*4.5*1000
    return json.dumps({ 
         'coeff': Coeff,
         'all lice': alllice,
         'name list': name_list,
         'current biomass':current_biomass,
         'year': year,
         'biomass knob':biomC,
         'lice/egg factor':liceData['lice knob']*liceData['egg factor'],
         }, cls= JsonEncoder)
     
@app.callback(
    [Output('LED_biomass','value'),
    Output('LED_egg','value')],
    #Input('bubbles','modified_timestamp'),
    Input('bubbles','data'),
)
def populate_LED(bubble_data):
    logger.info('modifying LED values')
    dataset= json.loads(bubble_data)
    return int(sum(dataset['coeff'])*1000), int(dataset['all lice']/24)
    
@app.callback(
    Output('planned_store','data'),
    Input('future_farms_toggle','on'),
    Input('planned_checklist','value'),
    Input('existing_farms_toggle','on'),
)
def store_planned_farms(toggle_planned, checklist, toggle_existing):
    return {'planned':toggle_planned, 
           'checklist':checklist, 
           'existing': toggle_existing}

@app.callback(
    Output('planned_checklist','options'),
    Output('planned_checklist','value'),
    Input('init','data')
    )
def init_checklist(init):
    logger.info('generating checklist')
    variables=json.loads(init)
    plans=[l[1] for l in variables['future_farms']]
    return plans, plans


@app.callback(
    [Output('heatmap', 'figure'),
    Output('heatmap_output', 'children'),
    Output('modal_div', 'children')
    ],
    [
    Input('theme_store',"data"),
      
    Input('span-slider','value') ,
    Input('trigger','n_clicks'),
    Input('init','data'),  
    Input('bubbles','data'),  
    ],
    [  
    State('heatmap','figure'),
    State('view_store','data'),
    State('planned_store', 'data'),   
    ],
)
def redraw( theme, span, trigger, init, bubble_data,  fig,  viewport, plan): 
    logger.info('drawing the map')
    ctx = dash.callback_context
    dataset= json.loads(bubble_data)
    viewdata= json.loads(viewport)
    theme=json.loads(theme)
    variables=json.loads(init)
    origin=[]
    is_open=False

    
    fig['layout']['template']=mk_template(theme['template'])
    fig['layout']['mapbox']['style']=theme['carto_style']
    fig['data'][0]['marker']['colorscale']=mk_colorscale(theme['cmp']) #mk_colorscale(theme['cmp'])
    fig['data'][0]['marker']['cmax']=span[1]
    fig['data'][0]['marker']['cmin']=span[0]
    fig['data'][2]['lat']=[variables['farm_data'][farm]['lat'] for farm in variables['farm_data'].keys()]
    fig['data'][2]['lon']=[variables['farm_data'][farm]['lon'] for farm in variables['farm_data'].keys()]
    fig['data'][2]['text']=[farm for farm in variables['farm_data'].keys()]
    fig['data'][3]['lat']=[l[3] for l in variables['future_farms']]
    fig['data'][3]['lon']=[l[-1] for l in variables['future_farms']]
    fig['data'][3]['text']=[l[1] for l in variables['future_farms']]
    fig['data'][3]['marker']['size']=[l[2] for l in variables['future_farms']]
    
    ### draw bubbles 
    fig['data'][1]=go.Scattermapbox(
                                lat=[variables['farm_data'][farm]['lat'] for farm in dataset['name list']],
                                lon=[variables['farm_data'][farm]['lon'] for farm in dataset['name list']],
                                text=dataset['name list'],
                                hovertemplate="<b>%{text}</b><br><br>" + \
                                        "Biomass: %{marker.size:.0f} tons<br>",
                                marker=dict(color='#62c462',
                                    size=dataset['current biomass'],
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    ),
                                name=f"Processed with biomass of may {dataset['year']}")
    fig['data'][1]['lat']=[variables['farm_data'][farm]['lat'] for farm in dataset['name list']]
    fig['data'][1]['lon']=[variables['farm_data'][farm]['lon'] for farm in dataset['name list']]
    fig['data'][1]['text']=dataset['name list']
    fig['data'][1]['hovertemplate']="<b>%{text}</b><br><br>" + "Biomass: %{marker.size:.0f} tons<br>"
    fig['data'][1]['marker']=dict(color='#62c462',
                                    size=dataset['current biomass'],
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    )
    fig['data'][1]['name']=f"Processed with biomass of may {dataset['year']}"                        
    
    ### update heatmap
    if ctx.triggered[0]['prop_id'] == 'trigger.n_clicks' or \
       ctx.triggered[0]['prop_id'] =='span-slider.value': 
        logger.debug(f"Existing toggle is {plan['existing']}, Planned toggle is {plan['planned']}")
        if plan['existing'] or plan['planned']:
            logger.info('rasterizing the heatmap')
            r = select_zoom(viewdata['zoom'])
            logger.debug('zoom: {}, resolution: {}'.format(viewdata['zoom'], r))
            super_ds, planned_ds=global_store(r)
            logger.info('global store loaded')
            if plan['existing']:
                logger.info('Cropping super ds')
                ds= crop_ds(super_ds, viewdata)
                name_list=dataset['name list'] # [1:] #### remove Achintraid because only NaN for some reason
                logger.info('Cropped')
                ds=ds[name_list]
                logger.info('Scaling the super ds with parameters')
                for i in range(len(name_list)):                    
                    ds[name_list[i]].values *=dataset['coeff'][i]
                logger.info('Scaled')    
                if plan['planned']:
                    logger.info('adding planned farms')
                    planned_ds=crop_ds(planned_ds, viewdata)/24
                    name_list=np.hstack((name_list,plan['checklist']))
                    for var in plan['checklist']:
                        ds[var]=planned_ds[var]*dataset['lice/egg factor']
                    logger.info('added and scaled planned farms')
                fig=render(fig, ds,span, theme, name_list)
            else:
                logger.info('adding only planned farms')
                if len(plan['checklist'])>0:
                    ds=crop_ds(planned_ds[plan['checklist']]*dataset['lice/egg factor'], viewdata)
                    name_list=plan['checklist']
                    fig=render(fig, ds, span, theme, name_list)
                else:
                    origin.append("no future")
                    is_open=True
                    fig['layout']['mapbox']['layers']=[]
        else:
            origin.append("no toggle")
            is_open=True
            fig['layout']['mapbox']['layers']=[]
    return fig, None, mk_modal(origin, is_open)
    
@app.callback(
    Output('inspect-button', 'children'),
    Output('inspect-button', 'disabled'),
    Input('heatmap','clickData'),
    Input('init','data'),
)
def grab_farm(select, data):
    if select is None:
        raise PreventUpdate
    else: 
        name= select['points'][0]['text']
        logger.debug (f"{name} was selected")
        variables=json.loads(data)
        l=[l[1] for l in variables['future_farms']]
        if name in l:
            return f'{name} has no record', True
        else:
            return f'Inspect {name} data', False 

#@app.callback(
#     Output('inspect-area', 'children'),
#     Output('inspect-area', 'disabled'),
#     Input('selection_store','data'),)
#def activate_inspection(data):
#    if data is None:
#        raise PreventUpdate
#    else:
#        return 'Open the area inspection tab', True     


@app.callback(
    Output('all_tabs', 'active_tab'),
    Output('dropdown_farms', 'value'),
    Input('inspect-button', 'n_clicks'),
    State('inspect-button', 'children'),
    )
def inspect_farm(click, name):
    logger.debug('Inspecting farm')
    if click is None or name== 'Select a farm on the map for inspection':
        raise PreventUpdate   
    return 'tab-graph', name[8:-5]

@app.callback(
    Output('dropdown_farms', 'options'),
    Input('init', 'data')
)
def populate_dropdown(init):
    logger.info('populating farm dropdown')
    logger.debug(f' serialised: {init[10980:11000]}')
    variables=json.loads(init)
    return variables['All_names']


@app.callback([
    Output('progress-curves','figure'),
    Output('farm_layout','children'),
],
    Input('dropdown_farms', 'value'),
    Input('theme_store', "data"),
    Input('init','data'),
    State('progress-curves','figure'),
)
def farm_inspector(name, theme, init, curves):
    theme=json.loads(theme)
    variables=json.loads(init)
    template = theme['template']    
    logger.debug(f'curve name: {name}')  
    time_range=   np.array([variables['times'][0],variables['lice_data']['coords']['time']['data'][-1]], dtype='datetime64[D]')#convert_dates()
    if not name:
        raise PreventUpdate
    else:
        for i in range(4): # try to 0 de values
            curves['data'][i]['x']=[None]
            curves['data'][i]['y']=[None]
        curves['data'][0]['x']=np.array(variables['times'], dtype='datetime64[D]')
        curves['data'][0]['y']=variables['farm_data'][name]['biomasses']
        curves['data'][1]['x']=np.array(variables['lice time'], dtype='datetime64[D]')
        curves['data'][1]['y']=variables['farm_data'][name]['lice data']
        curves['data'][2]['y']=[0.5,0.5]
        curves['data'][2]['x']= time_range 
        curves['data'][3]['x']= time_range 
        curves['data'][3]['y']=[variables['farm_data'][name]['mean lice'], variables['farm_data'][name]['mean lice']]      
        #curves=farm_plot(name, variables['times'], variables['farm_data'][name], variables['lice_data'], template)
        curves['layout']['template']=mk_template(template)
        logger.debug(curves)
        return curves, mk_farm_layout(name, marks_biomass,marks_lice, variables['farm_data'][name])

    
@app.callback(
    Output("collapse_select_contributor", "is_open"),
    Input("collapse_button_select_contributor",'n_clicks'),
    State("collapse_select_contributor", "is_open"),
)
def open_selected_future_farms(n, is_open):
    logger.debug('Collapsing contributor')
    if n:
        return not is_open
    return is_open

@app.callback(
    Output("collapse_tune", "is_open"),
    Input("collapse_button_tune",'n_clicks'),
    State("collapse_tune", "is_open"),
)
def open_selected_future_farms(n, is_open):
    logger.debug('Collapsing tuning')
    if n:
        return not is_open
    return is_open


@app.callback(
    Output("tab2_store",'data'),
    # Output('all_tabs', 'active_tab'),
#    Input('inspect-area', 'n_clicks'),    
    Input('selection_store','data'),
    Input('view_store','data'),
#    State('inspect-area', 'children'),
    )
def compute_selection_stats(selection,view):
    selection=json.loads(selection)
    tab2={'counts':{},
          'max':{},
          'mean':{},
          'stdv':{}}
    if len(selection[0]['coordinates'])==0:
        raise PreventUpdate   
    else:
        
        r = select_zoom(json.loads(view)['zoom'])
        super_ds, planned_ds=global_store(r)
        cropped_current=super_ds.rio.write_crs(3857, inplace=True).rio.clip(selection, crs=4326)
        cropped_planned=planned_ds.rio.write_crs(3857, inplace=True).rio.clip(selection, crs=4326).compute()
    ### statistics counts of cells with values, max concentrations, average, stdv    
        for ds in [cropped_current, cropped_planned]:
            for farm in ds.keys():
                arr= ds[farm].compute()
                if arr.count().item()>0:
                    tab2['counts'][farm], tab2['max'][farm], tab2['mean'][farm], tab2['stdv'][farm]=arr.count().item(), arr.max().item(), arr.mean().item(), arr.std().item()
    logger.debug('tab2 data stored')
    return json.dumps(tab2, cls= JsonEncoder)

@app.callback(
    Output('counts','figure'),
    Output('maxis','figure'),
    Output('means','figure'),
    Output('standev','figure'),## all the graphs
    Input("tab2_store",'data'),
    State('counts','figure'),
    State('maxis','figure'),
    State('means','figure'),
    State('standev','figure')
)    
def draw_statistics(tab2, fig1,fig2,fig3,fig4):
    stats=json.loads(tab2)
    logger.debug(f'tab2_{tab2}')
    for val,fig in zip(['counts','max','mean','stdv'],[fig1,fig2,fig3,fig4]):
        fig['data'][0]['x']=list(stats[val].keys())
        fig['data'][0]['y']=list(stats[val].values())
    return fig1, fig2, fig3, fig4
    
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True)
