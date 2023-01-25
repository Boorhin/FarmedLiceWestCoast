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
import json, logging
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
import os.path
import dash
# from dash import dcc as dcc
from dash.exceptions import PreventUpdate
#from dash import html as html
# from dash.dependencies import Input, Output, State, MATCH, ALL
from dash_extensions.enrich import Output, Input, html, State, MATCH, ALL, DashProxy, LogTransform, DashLogger, dcc, ServersideOutput, ServersideOutputTransform, FileSystemStore
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template
import dash_mantine_components as dmc

import dash_daq as daq

from flask_caching import Cache
from dash.exceptions import PreventUpdate

from layout import *
from preprocess import *

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        #elif isinstance(obj, datetime):
        #    return (str(obj))
        else:
            return json.JSONEncoder.default(self, obj)

def get_coordinates(arr):
    logger.debug('compute corner coordinates of filtered dataset')
    coordinates=np.zeros((4,2))
    coordinates[0]=p(arr.x.values[0],arr.y.values[0], inverse=True)
    coordinates[1]=p(arr.x.values[-1],arr.y.values[0], inverse=True)
    coordinates[2]=p(arr.x.values[-1],arr.y.values[-1], inverse=True)
    coordinates[3]=p(arr.x.values[0],arr.y.values[-1], inverse=True)
    return coordinates[::-1]
    
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
    return tf.shade(arr.where(arr>0).load(),
                    cmap=cmp, how='linear',
                    span=span).to_pil()

def select_zoom(zoom):
    '''
    select the zarr resolution according to the zoom for preselection 
    trying to match https://docs.mapbox.com/help/glossary/zoom-level/
    '''
    if zoom <6:
        r=800
    elif zoom>9:
        r= 50
    elif 6<=zoom<7:
        r=400
    elif 7<=zoom<8:
        r=200
    elif 8<=zoom<9:
        r=100
    return r
    
def fetch_biomass(farm_data, lice_data, activated_farms, biomass_factor, lice_factor, tree, times, ref_biom, Ids, year=2021):
    '''
    Identify the biomass data for the month of may of the chosen year
    scale the data according to data
    remove farm with no data for the month
    try to populate the lice density for each farm
    may 2003 has no data and generate error
    '''
    n= 50 #nb of nearest farms
    start, end = datetime(year=year, month=4,day=30), datetime(year=year, month=6,day=1)
    filters=np.where(np.logical_and(times> start, times<end))[0]
    filtered=times[filters]
    for farm in farm_data.keys():       
        extract=farm_data[farm]['biomasses'][filters].mean()
        if np.isnan(extract):
            activated_farms[farm_data[farm]['ID']]= False
        else:
            biomass_factor[farm_data[farm]['ID']]=extract/farm_data[farm]['reference biomass']
            ref_biom[farm_data[farm]['ID']]=farm_data[farm]['reference biomass']
            local_data=search_lice_data(start,end, farm_data[farm]['Site ID Scot env'], farm, lice_data, farm_data)
            if local_data is not None :
                lice_factor[farm_data[farm]['ID']]=local_data
            else:
                seek= tree.query(np.array([farm_data[farm]['lon'], farm_data[farm]['lat']]).T, n)[1]
                for i in range(n):
                    remote_data= search_lice_data(start,end, Ids[i], farm, lice_data, farm_data)
                    if remote_data is not None :
                        lice_factor[farm_data[farm]['ID']]=remote_data
                        break
    return activated_farms, biomass_factor, lice_factor, ref_biom      


#### SET LOGGER #####
logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('sealice_logger')
logger.setLevel(logging.DEBUG)
autocl=2000 #time to close notification

############# VARIABLES ##########################33
 # value extent
resolution=[50,100,200,400,800]
zooms=[9,8,7,6,5]
start, end = "2018-05-01", "2018-05-31"
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
if os.path.exists('/mnt/nfs/data/'):
    rootdir='/mnt/nfs/data/'
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


######### APP DEFINITION ############
my_backend = FileSystemStore(cache_dir="/tmp")
app = DashProxy(__name__,
                external_stylesheets=[url_theme1],#, dbc_css
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
                transforms=[LogTransform(), ServersideOutputTransform(backend=my_backend)]
                )
server=app.server
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/tmp'
})
timeout = 300

@server.route('/_ah/warmup')
def warmup():
    """Warm up an instance of the app."""
    return "it is warm"
    # Handle your warmup logic here, e.g. set up a database connection pool


app.title="Heatmap Dashboard"
app.layout = dbc.Container([
    #Store
    html.Div([
        dcc.Store(id='init', storage_type='session'),
        dcc.Store(id='bubbles', storage_type='session'),
        dcc.Store(id='lice_store', storage_type='session'),
        dcc.Store(id='view_store', storage_type='session'),
        dcc.Store(id='theme_store', storage_type='session'),
        dcc.Store(id='planned_store', storage_type='session'),
        dcc.Store(id='fig_store', storage_type='session'),
        
    #header
        html.Div([ 
            html.Img(src='assets/logo.svg',
                     width=96,
                     alt='logo',
                     style={'float':'right', 'padding':'5px'},
                     className='logo'),          
            html.H1('Scottish Westcoast artificial sealice infestation'),
            ThemeSwitchAIO(aio_id='theme',
                    icons={"left": "fa fa-sun", "right": "fa fa-moon"},
                    themes=[url_theme1, url_theme2])
            ]),
    # Define tabs
        html.Div([
            dbc.Tabs(id='all_tabs',
                children= [
                dbc.Tab(tab1_layout(),label='Interactive map',tab_id='tab-main',),
                #dbc.Tab(tab2_layout(farm_data, marks_biomass,marks_lice),label='Tuning dashboard',tab_id='tab-tunning',),
                dbc.Tab(tab3_layout(),label='Farm data inspection',tab_id='tab-graph',),
                #dbc.Tab(tab4_layout(farm_data), label='All farms toggles', tab_id='tab-toggle'),
                ])
            ])
        ])
], fluid=True, className='dbc')


@cache.memoize()
def global_store(r):
    pathtods=f'curr_{r}m.zarr'
    pathtofut=f'planned_{r}m.zarr'
    logger.info(f'using global store {pathtods}')
    super_ds=open_zarr(rootdir+pathtods) #.drop('North Kilbrannan')
    planned_ds= open_zarr(rootdir+pathtofut)
    ## remove border effects
    super_ds= super_ds.where(super_ds.x<-509600)   
    return super_ds, planned_ds
    
@app.callback(
     ServersideOutput('init', 'data'),
     Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
     log = True
)
def initialise_var(toggle, dash_logger: DashLogger):
    logger.info('Preparing dataset')
    variables={}
    dash_logger.info('Initialising ...', autoClose=autocl)
    master='curr_800m.zarr'
    super_ds=open_zarr(rootdir+master)
    variables['All_names']=np.array(list(super_ds.keys()))
    variables['future_farms']=read_future_farms(rootdir+'future_farms.txt')
    variables['ref_biom']=np.zeros(len(variables['All_names']))
    liceStore='consolidated_sealice_data_2017-2021.zarr'
    lice_data=open_zarr(rootdir+liceStore)
    ### Correct typos in the raw data
    id_c=250
    typos =['Fs0860', 'Fs1018', 'Fs1024'] 
    correct=['FS0860', 'FS1018', 'FS1024']
    for mess, ok in zip(typos, correct):
        lice_data[ok].values[id_c]=lice_data[mess].values[id_c]
        lice_data=lice_data.drop(mess)
    variables['lice_data']=lice_data
    csvfile='biomasses.csv'
    variables['farm_data'], variables['times'], variables['tree'], variables['Ids'] =read_farm_data(rootdir+csvfile, lice_data)
    logger.info('Farm loaded')
    sepacsv= 'SEPA_GSID.csv'
    variables['farm_data']=add_new_SEPA_nb(rootdir+sepacsv, variables['farm_data'])
    logger.info('Variables loaded')
    return [variables]

@app.callback(
    Output('theme_store', 'data'),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
    log= True 
)
def record_theme(toggle, dash_logger: DashLogger):
    dash_logger.info('Switching themes', autoClose=autocl)
     ### toggle themes    
    theme={}
    theme['template'] = template_theme1 if toggle else template_theme2
    theme['cmp']= cmp1 if toggle else cmp2
    theme['carto_style']= carto_style1 if toggle else carto_style2
    return json.dumps(theme)

@app.callback(
    Output('egg_toggle_output','children'),
    Input('egg_toggle','on'),
    log=True
)
def toggle_egg_models(eggs, dash_logger: DashLogger):
    dash_logger.info('Egg production model changed', autoClose=autocl)
    if eggs:
        return 'Stien (2005)'
    else:
        return 'Rittenhouse et al. (2016)'

@app.callback(
    ServersideOutput('lice_store','data'),
    [Input('lice_knob','value'),
    Input('egg_toggle','on'),
    Input('lice_meas_toggle','on'),
    Input('init','data'),],
    log=True
    )
def compute_lice_data(liceC, egg, meas, variables, dash_logger: DashLogger):
    logger.info('scaling lice')
    logger.debug(f'egg is {egg}')
    dash_logger.info('Lice data are being scaled', autoClose=autocl)
    variables=variables[0]
    # modify egg model from Rittenhouse (16.9) to Stein (30)
    if egg:
        # lices *= 30/16.9
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
    Input('heatmap', 'relayoutData'),
    log=True
    )
def store_viewport(relay, dash_logger: DashLogger):
    dash_logger.info('Updating viewport data', autoClose=autocl)
    logger.debug('Storing viewport data')
    logger.debug(f'relay:    {relay}')
    if relay is not None:
        zoom=relay['mapbox.zoom']
        bbox=relay['mapbox._derived']['coordinates']
    else:
        zoom=5.
        bbox=[[-16., 60.], 
            [5., 60.], 
            [5., 53.], 
            [-16., 53.]]
    corners=calculate_edge(np.array(bbox))
    #corners['bbox']=bbox
    corners['zoom']=zoom
    return json.dumps(corners)
    
        

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
    log=True
)
def mk_bubbles(year, biomC,lice_tst, variables, liceData, meas, dash_logger: DashLogger):
    dash_logger.info('Scaled biomass according to chosen parameters', autoClose=autocl)
    #liceData=json.loads(lice_data)
    #variables=json.loads(init)
    liceData=liceData[0]
    variables=variables[0]
    activated_farms= np.ones(len(variables['All_names']), dtype='bool')
    Coeff=np.ones(len(variables['All_names'])) 
    biomass_factor=np.ones(len(variables['All_names']))
    lice_factor=liceData['lice factor']
    if biomC ==0:
        biomC=0.00001
    biomC /=100
    logger.info('preparing lice factor')
    idx, biomass_factor, lice_factor, ref_biom=fetch_biomass(variables['farm_data'], variables['lice_data'], 
                                                     activated_farms, biomass_factor, lice_factor, variables['tree'], 
                                                     variables['times'], variables['ref_biom'], variables['Ids'], year)
    # overwrite the computed lice... needs to change
    if not meas:
        lice_factor=liceData['lice factor']
    #dash_logger.info('Biomass and lice scaled', autoClose=autocl)
    name_list=np.array(list(variables['farm_data'].keys()))[idx]    
    ##### update discs farms
    current_biomass=[variables['farm_data'][farm]['reference biomass']*
                                    biomass_factor[variables['farm_data'][farm]['ID']] *biomC
                                    for farm in name_list]
        # set global factor biomass x individual farm biom x individual lice x egg model
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
         }, cls=NumpyEncoder)
     
@app.callback(
    [Output('LED_biomass','value'),
    Output('LED_egg','value')],
    #Input('bubbles','modified_timestamp'),
    Input('bubbles','data'),
    log=True
)
def populate_LED(bubble_data, dash_logger: DashLogger):
    logger.info('modifying LED values')
    dash_logger.info('Modifying LED values', autoClose=autocl)
    dataset= json.loads(bubble_data)
    return int(sum(dataset['coeff'])*1000), int(dataset['all lice'])
    
@app.callback(
    ServersideOutput('planned_store','data'),
    Input('future_farms_toggle','on'),
    Input('planned_checklist','value'),
    Input('existing_farms_toggle','on'),
    log=True
)
def store_planned_farms(toggle_planned, checklist, toggle_existing, dash_logger: DashLogger):
    dash_logger.info('Storing selected planned farms', autoClose=autocl)
    return [{'planned':toggle_planned, 'checklist':checklist, 'existing': toggle_existing}]

@app.callback(
    Output('planned_checklist','options'),
    Input('init','data')
    )
def init_checklist(variables):
    logger.info('generating checklist')
    return variables[0]['future_farms']['Name']


@app.callback(
    [Output('heatmap', 'figure'),
    Output('heatmap_output', 'children'),
    ],
    [
    Input('theme_store',"data"),
    Input('planned_store', 'data'),  
    Input('span-slider','value') ,
    #Input('bubbles','modified_timestamp'),
    Input('trigger','n_clicks'),
    Input('init','data'),  
    Input('bubbles','data'),  
    ],
    [  
    State('heatmap','figure'),
    
    #State('heatmap', 'figure'),
    State('view_store','data')   
    ],
    log=True
)
def redraw( theme, plan, span, trigger, variables, bubble_data,  fig,  viewport, dash_logger: DashLogger): #, bubble_tmst
    dash_logger.info('Updating the map', autoClose=autocl)
    logger.info('drawing the map')
    # logger.debug(f'figure:     {fig}')
    ctx = dash.callback_context
    variables=variables[0]
    #dataset=dataset[0]
    #viewdata=viewdata[0]
    #theme=theme[0]
    plan=plan[0]
    # logger.debug(ctx.triggered)
    dataset= json.loads(bubble_data)
    viewdata= json.loads(viewport)
    theme=json.loads(theme)
    # plan=json.loads(plan_data)
    # variables=json.loads(init)
    # fig=json.loads(fig_data)
    
    fig['layout']['template']=mk_template(theme['template'])
    fig['layout']['mapbox']['style']=theme['carto_style']
    fig['data'][0]['marker']['colorscale']=mk_colorscale(theme['cmp']) #mk_colorscale(theme['cmp'])
    fig['data'][0]['marker']['cmax']=span[1]
    fig['data'][0]['marker']['cmin']=span[0]
    fig['data'][2]['lat']=[variables['farm_data'][farm]['lat'] for farm in variables['farm_data'].keys()]
    fig['data'][2]['lon']=[variables['farm_data'][farm]['lon'] for farm in variables['farm_data'].keys()]
    fig['data'][2]['text']=[farm for farm in variables['farm_data'].keys()]
    fig['data'][3]['lat']=variables['future_farms']['Lat']
    fig['data'][3]['lon']=variables['future_farms']['Lon']
    fig['data'][3]['text']=variables['future_farms']['Name']
    fig['data'][3]['marker']['size']=variables['future_farms']['Biomass_tonnes']
    
    ### draw bubbles 
    #if ctx.triggered[0]['prop_id'] == 'bubbles.data':
    dash_logger.info('Updating farm discs', autoClose=autocl)  
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
        
    dash_logger.info('Farm discs updated', autoClose=autocl)  
    
    ### update heatmap
    if ctx.triggered[0]['prop_id'] == 'trigger.n_clicks' or \
       ctx.triggered[0]['prop_id'] =='span-slider.value': 
        if plan['existing'] or plan['planned']:
            dash_logger.info('Updating the density map', autoClose=autocl)
            logger.info('rasterizing map')
            r = select_zoom(viewdata['zoom'])
            logger.debug('zoom: {}, resolution: {}'.format(viewdata['zoom'], r))
            super_ds, planned_ds=global_store(r)
            logger.info('global store loaded')
            if plan['existing']:
                ds= super_ds
                name_list=dataset['name list'][1:] #### remove Achintraid because only NaN for some reason
                logger.debug(f'name list:    {name_list}')
                ds=ds[name_list]
                for i in range(len(name_list)):
                    ds[name_list[i]].values *=dataset['coeff'][i]
                if plan['planned']:
                    name_list=np.hstack((name_list,plan['checklist']))
                    for var in plan['checklist']:
                        ds[var]=planned_ds[var]*dataset['lice/egg factor']
            else:
                if len(plan['checklist'])>0:
                    ds=planned_ds[plan['checklist']]*dataset['lice/egg factor']
                    name_list=plan['checklist']
                else:
                    dash_logger.warning('No farm choosen in the checklist')
                    raise PreventUpdate
            subds=ds.where((ds.x<viewdata['xmax'] ) &
                           (ds.x>viewdata['xmin'] ) &
                           (ds.y>viewdata['ymin'] ) &
                           (ds.y<viewdata['ymax'] ))
            coordinates=get_coordinates(subds)
            logger.debug(f'subds:      {subds}')
            logger.debug(f'name_list:   {name_list}')
            logger.debug(f'coordinates:     {coordinates}')
            fig['layout']['mapbox']['layers']=[{
                                        "below": 'traces',
                                        "sourcetype": "image",
                                        "source": mk_img(subds, span, theme['cmp']),
                                        "coordinates": coordinates
                                    },]
            logger.info('raster loaded')
            dash_logger.info('Density map updated', autoClose=autocl)
        else:
            dash_logger.warning('Neither existing or planning farms are toggled on')
            raise PreventUpdate
        #    fig['layout']['mapbox']['layers']=[]

    return fig, None

@app.callback(
    Output('dropdown_farms', 'options'),
    Input('init', 'data')
)
def populate_dropdown(variables):
    logger.info('populating farm dropdown')
    variables=variables[0]
    return variables['All_names']


@app.callback([
    Output('progress-curves','figure'),
    Output('farm_layout','children'),
],
    Input('dropdown_farms', 'value'),
    Input('theme_store', "data"),
    Input('init','data'),
    State('progress-curves','figure'),
    log= True
)
def farm_inspector(name, theme, init, curves, dash_logger: DashLogger):
    #theme=theme[0]
    theme=json.loads(theme)
    variables=init[0]
    template = theme['template']    
    logger.debug(f'curve name: {name}')  
    time_range=   np.array([variables['times'][0],variables['lice_data'].time.values[-1]], dtype='datetime64[D]')#convert_dates()
    if not name:
        dash_logger.warning('No farm selected', autoClose=autocl)
        raise PreventUpdate
    else:
        dash_logger.info(f'Computing curve for {name}', autoClose=autocl)
        for i in range(4): # try to 0 de values
            curves['data'][i]['x']=[None]
            curves['data'][i]['y']=[None]
        curves['data'][0]['x']=variables['times'].astype('datetime64[D]')
        curves['data'][0]['y']=variables['farm_data'][name]['biomasses']
        curves['data'][1]['x']=variables['lice_data'].time.values.astype('datetime64[D]')
        curves['data'][1]['y']=variables['farm_data'][name]['lice data']
        curves['data'][2]['y']=[0.5,0.5]
        curves['data'][2]['x']= time_range 
        curves['data'][3]['x']= time_range 
        curves['data'][3]['y']=[variables['farm_data'][name]['mean lice'].values, variables['farm_data'][name]['mean lice'].values]      
        #curves=farm_plot(name, variables['times'], variables['farm_data'][name], variables['lice_data'], template)
        curves['layout']['template']=mk_template(template)
        logger.debug(curves)
        return curves, mk_farm_layout(name, marks_biomass,marks_lice, variables['farm_data'][name])

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True)
