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
#from google.cloud import storage
import numpy as np
from scipy.spatial import KDTree
from pyproj import Proj
# from random import random
import datashader as DS
import plotly.graph_objects as go
#from plotly.supblots import make_subplots
from colorcet import fire, bmy
from datashader import transfer_functions as tf
from datetime import datetime, timedelta
import os.path
import dash
from dash import dcc as dcc
from dash import html as html
from dash.dependencies import Input, Output, State, MATCH, ALL
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template

import dash_daq as daq

from flask_caching import Cache
from dash.exceptions import PreventUpdate

#from callbacks import callbacks

def get_coordinates(arr):
    coordinates=np.zeros((4,2))

    coordinates[0]=p(arr.x.values[0],arr.y.values[0], inverse=True)
    coordinates[1]=p(arr.x.values[-1],arr.y.values[0], inverse=True)
    coordinates[2]=p(arr.x.values[-1],arr.y.values[-1], inverse=True)
    coordinates[3]=p(arr.x.values[0],arr.y.values[-1], inverse=True)

    #print(coordinates)
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
       box[i]=p(coordinates[i])
    return box

def mk_img(ds_host, name_list, span, Coeff,cmp):
    '''
    Create an image to project on mabpox
    '''
    print('making raster...')
    subds=ds_host[name_list]
    for i in range(len(name_list)):
        subds[name_list[i]].values *=Coeff[i]
    arr= subds.to_stacked_array('v', ['y', 'x']).sum(dim='v')
    print('data stacked')
    #lat=[56.8, 56.3, 56.15, 56.65, 56.8]
    #lon=[-8, -7.45,-7.7, -8.2, -8]

    polyg= [{"type":"Polygon",
              "coordinates":[[
              [-890556, 7719350],
              [-829330, 7618370],
              [-857160, 7588335],
              [-912820, 7688916],
              [-890556, 7719350]
              ]]
              }
          ]
    arr= arr.rio.write_crs(3857, inplace=True).rio.clip(polyg, invert=True, crs=3857)
    print('data cropped')
    
    return tf.shade(arr.where(arr>0).load(),
                    cmap=cmp, how='linear',
                    span=span).to_pil()
def add_new_SEPA_nb(sepafile):
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
               print(f'{line[0]} not found in farmdata')
    return farm_data

def read_farm_data(farmfile):
    data={}
    print('########## READING BIOMASS DATA #######')
    with open(farmfile) as f:
        head=f.readline().strip().split(',')[21:]
        times = np.array([datetime.strptime(h,'%m/%d/%Y') for h in head])
        f.readline()
        id=0
        for line in f:   
            line=line.strip().split(',')
            #print('Reading data for - ', line[0])
            data[line[0]]= {'additional location':line[1],
                            'Name MS': line[2],
                            'Site ID SEPA': line[3],
                            'Site ID Scot env':str(line[4]),
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
            data[line[0]]['lice data'], data[line[0]]['mean lice']=add_lice_data(line[4])       
            if ref==0:
                # print('NDV in ',line[0]) 
                id -=1 
                del data[line[0]]
            #ref_biom[id]=ref
    print('########## BIOMASS DATA READ ###########')
    print('########## Making KDe Tree   ###########')
    Xs= np.array([data[farm]['lon'] for farm in data.keys()])
    Ys= np.array([data[farm]['lat'] for farm in data.keys()])
    Ids=np.array([data[farm]['Site ID Scot env'] for farm in data.keys()])
    # print(Ids)
    tree = KDTree(np.vstack((Xs,Ys)).T)
    print('########## Tree Made ############')
    return data, times, tree, Ids

def add_lice_data(SEPA_ID):
    arr= np.empty(261)
    arr[:]=np.nan
    av=np.nan
    for licence in lice_data.keys():
        if licence==SEPA_ID:
            arr=lice_data[licence].values
            av = lice_data[licence].mean()
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
    
def search_lice_data(start,end, ident, farm):
    '''
    Search if there are data for the farm at the chosen date.
    Check it is not null
    return may data if available
    if not, try to return the average lice value for the farm.
    '''
    if len(ident) >0:
        # print(ident, farm)
        may_data= lice_data[ident].sel(time=slice(start,end)).mean().values
        if not np.isnan(may_data):
            if may_data>0:
                # print(f'found lice data in may for {farm}, {ident}')
                return may_data
        else:
            if np.isnan(farm_data[farm]['mean lice']) is False:
                # print('Using average data for the farm ', farm)
                return fmay_dataarm_data[farm]['mean lice']
    else:
        print(f'No ID for farm {farm}')

    
def fetch_biomass(activated_farms, biomass_factor, lice_factor, year=2004):
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
            # print(f'{farm} is not stocked')
        else:
            biomass_factor[farm_data[farm]['ID']]=extract/farm_data[farm]['reference biomass']
            ref_biom[farm_data[farm]['ID']]=farm_data[farm]['reference biomass']
            local_data=search_lice_data(start,end, farm_data[farm]['Site ID Scot env'], farm)
            if local_data is not None :
                lice_factor[farm_data[farm]['ID']]=local_data
            else:
                # print('searching nearby farms')
                seek= tree.query(np.array([farm_data[farm]['lon'], farm_data[farm]['lat']]).T, n)[1]
                for i in range(n):
                    remote_data= search_lice_data(start,end, Ids[i], farm)
                    if remote_data is not None :
                        lice_factor[farm_data[farm]['ID']]=remote_data
                        # print(f'Used data from {Ids[i]} to populate {farm}')
                        break
    return activated_farms, biomass_factor, lice_factor, ref_biom

        
#####################TAB 1 ###########################

def make_base_figure(farm_data, center_lat, center_lon, span, cmp, template):
    print('Making figure ...')
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorscale=cmp,
                        cmax=span[1],
                        cmin=span[0],
                        showscale=True,

                        ),
                    name='only_scale',
                    showlegend=False),)
    fig.add_trace(go.Scattermapbox())
    fig.add_trace(go.Scattermapbox(
                                lat=[farm_data[farm]['lat'] for farm in farm_data.keys()],
                                lon=[farm_data[farm]['lon'] for farm in farm_data.keys()],
                                text=[farm for farm in farm_data.keys()],
                                marker=dict(color='#e9ecef', size=4, showscale=False),
                                name='Mapped farms'))

    #fig.add_trace((go.Scattermapbox(lat=[56.8, 56.3, 56.15, 56.65],
    #                                lon=[-8, -7.45,-7.7, -8.2], 
    #                                mode='lines')))
    fig.update_layout(
                height=512,
                width=1024,
                hovermode='closest',
                showlegend=False,
                margin=dict(b=3, t=5),
                template=template,
                mapbox=dict(
                    bearing=0,
                    center=dict(
                        lat=center_lat,
                        lon=center_lon,
                    ),
                    pitch=0,
                    zoom=5.5,
                    style="carto-darkmatter",
                    ))
    print('figure done.')
    return fig

def comment_card(start, end):
   return dbc.Card(
      dbc.CardBody([
                dbc.Alert('The size of the disks is proportional to the biomass.', color='primary'),
                dbc.Alert('Hover a farm for more information.', color='secondary'),
                dbc.Alert('Colorscale is the average density of copepodid per sqm from {} to {}.'.format(start,end), color='primary'),
                dbc.Alert('A density of 2 copepodid/sqm/day leads to a 30% mortality of wild smolts each day.', color='warning')
            ])
            )
def legend_card():
    return dbc.Card([
                dbc.CardHeader('Legend'),
                dbc.CardBody([
                    html.Span([
                dbc.Badge('Processed farms', color="success",pill=True),
                # dbc.Badge('Farms awaiting processing', color='info',pill=True),
                dbc.Badge('Farms included in the study', color='light', pill=True),
                    ]),
                ])
            ])

def tuning_card():
    return dbc.Card([
        dbc.CardHeader('Adjust biomass and lice infestation'),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    daq.Knob(
                        id='biomass_knob',
                        label='% Biomass',
                        value=100,
                        max=200,
                        # min=0.1,
                        scale={'start':0,'labelInterval':5,'interval':5},
                        color='#f89406'
                        )
                    ]),
                dbc.Col([
                    daq.Knob(
                        id='lice_knob',
                        label='Lice per fish',
                        value=0.5,
                        min=0.25,
                        max=8,
                        scale={'start':0, 'labelInterval':10,'interval':0.05},
                        color='#f89406'
                        )
                    ]),
                dbc.Col([
                    daq.BooleanSwitch(
                         id='lice_meas_toggle',
                         label='Use reported lice',
                         on=False
                         ),
                    html.P("Very little data are available on lice infestation. The algorythm will try first to find if there are data in the May season you selected. If there isn't it will try to make an average of recorded lice for the farm. If the farm never reported lice counts then it will use the nearest farm that has data.")
                    ]),
                ])
            ])
        ])

def mk_map_pres(): #
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader('Continuous map update'),
                dbc.CardBody([
                    daq.PowerButton(
                    	id='power_streaming',
                    	on=False),
                    html.Div(id='power_streaming_result')
                    ])
                ]),
            dbc.Card([
                            dbc.CardHeader('Choose the egg production model'),
                            dbc.CardBody(
                                dbc.Row([
                                    html.Div([
                                    daq.BooleanSwitch(
                                        id='egg_toggle',
                                        on=True
                                        ),
                                    html.Div(
                                        id='egg_toggle_output',
                                        style={'text-align':'center'}
                                        ),])
                                ])
                            )
                        ])
        ],width=3),
        dbc.Col([
            tuning_card()
        ],width=9),
    ]),

def tab1_layout(farm_data,center_lat, center_lon, span, cmp, template):
    return dbc.Card([
    dbc.CardHeader('Control dashboard'),
    dbc.CardBody([
        dbc.Card([
            dbc.CardBody(mk_map_pres())
        ]),
        dbc.Card([
            dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dcc.Graph(
                        id='heatmap',
                        figure=make_base_figure(farm_data, center_lat, 
                                   center_lon, span, cmp, template)
                        ),
                    dcc.Loading(
                        id='figure_loading',
                        children=[html.Div(id='heatmap_output'),],
                        type='graph',
                        fullscreen=True
                        )
                    ], width=10),
                dbc.Col([
                    html.P(
                                children='(copepodid/sqm/day)',
                                style={'writing-mode':'vertical-rl'},
                                ),
                    ], width=1),
                dbc.Col([
                     html.P('Scale range'),
                     dcc.RangeSlider(
                                id='span-slider',
                                min=0,
                                max=20,
                                step=0.5,
                                marks={n:'%s' %n for n in range(21)},
                                value=[0,2],
                                vertical=True,
                                )
                    ], width=1)
                ], align='center', className="g-0")
            ])
        ]),
        dbc.Card([
            dbc.CardHeader('Production year'),
            dbc.CardBody([
                dbc.Row([
                    html.P('Choose the year of production'),
                    dcc.Slider(
                                id='year_slider',
                                step=1,
                                min=2004,
                                max=2021,
                                marks={
                                       2005:'2005',
                                       2007:'2007',
                                       2009:'2009',
                                       2011:'2011',
                                       2013:'2013',
                                       2015:'2015',
                                       2017:'2017',
                                       2019:'2019',
                                       2021:'2021'},
                                value=2021,
                                tooltip={"placement": "bottom"}),
                ]),
                dbc.Row([
                    dbc.Col([
                        daq.LEDDisplay(
                            id='LED_biomass',
                            label='Total fish farmed in may (kg)',
                            color='#f89406',
                            backgroundColor='#7a8288',
                            ),
                        ]),
                    dbc.Col([
                        daq.LEDDisplay(
                            id='LED_egg',
                            label='Daily release of sealice nauplii from fish farms',
                            color='#f89406',
                            backgroundColor='#7a8288',
                            ), 
                        ]),
                    ]),
                ]),
            ]),
        ]),
    ])
    #])

################# tab2 ###########################3


def tab2_layout(farm_data, marks_biomass,marks_lice):

    layout= dbc.Card([
    ])
    return layout

################### TAB 3 #########################


def mk_farm_evo(name, times):    
    '''
    Plot individual farm biomass
    '''   
    fig_p=go.Figure()
    fig_p.add_trace(go.Scatter(
           x= times,
           y= farm_data[name]['biomasses'],
           mode='lines+markers',
           name='Biomass',
           yaxis='y1',
       ))

    fig_p.add_trace(go.Scatter(
        x=lice_data.time,
        y=farm_data[name]['lice data'],
        mode='lines+markers',
        name='lice count',
        yaxis='y2',
        ))
    fig_p.add_shape(type='line', xref='paper', 
        x0=0, y0=0.5, x1=1, y1=0.5,
        line=dict(color='#f89406', dash='dash'),
        name='modelled lice infestation',
        yref='y2'
        )
    if not np.isnan(farm_data[name]['mean lice']):
        fig_p.add_shape(type='line', xref='paper', 
            x0=0, y0=float(farm_data[name]['mean lice']), x1=1, y1=float(farm_data[name]['mean lice']),
            line=dict(color='firebrick', dash='dash'),
            name='Average lice infestation',
            yref='y2'
            )   
    for y in range(2003,2022):
        fig_p.add_vline(x=datetime(year=y, month=5, day=1), line=dict(color='green', dash='dash'))
    fig_p.update_layout(
        yaxis= dict(title='Recorded fish farmbiomass (tons)',
                    showgrid=False ),
        yaxis2=dict(title='Reported average lice/fish',
                     overlaying='y', 
                     side='right',
                     showgrid=False ),
        margin=dict(b=15, l=15, r=5, t=5),
    )
    # print(fig_p['layout']['shapes'][0])
    return fig_p
    
def togglingyears():
    p='Production year '
    if farm_data[name]['Prod year'] == 'ODD':
        p+='odd'
        s=True
    elif farm_data[name]['Prod year'] == 'EVEN':
        p+= 'even'
        s= False
    else:
        p+= farm_data[name]['Prod year']
        s= random() < 0.5,
    
def mk_farm_layout(name, marks_biomass,marks_lice):
    farm_lay= [dbc.Col([
    		    dbc.Row(
                	daq.BooleanSwitch(
                 	   id={'type':'switch','id':farm_data[name]['ID']},
                	    on=True,
                	    label="Toggle farm on/off",
                	    labelPosition="top"
                	    )),

              	     dbc.Row([
              	          html.P('Site identification number (GSID): '+farm_data[name]['GSID']),
              	          html.P('SEPA Reference: ' + farm_data[name]['Site ID SEPA']),
              	          html.P('Marine Scotland Reference: ' + farm_data[name]['Site ID Scot env']),
              	          html.P('Marine Scotland site name: ' + farm_data[name]['Name MS']),
              	          #html.P('Production Year: '+ farm_data[name]['Prod year']),
              	          html.P('Operator: ' + farm_data[name]['operator']),
              	          ]),
                   ], width=3),
            dbc.Col([
                html.H3('Modelled Peak Biomass {} tons'.format(farm_data[name]['reference biomass'])),
                html.H3('Average lice per fish {}'.format(np.round(farm_data[name]['mean lice'],2))),
                html.H3('Tune Farm biomass: (DESACTIVATED)'),
                dcc.Slider(
                    id={'type':'biomass_slider','id':farm_data[name]['ID']},
                    step=0.05,
                    marks=marks_biomass,
                    value=1,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=True,
                    ),
                html.H3('Tune lice infestation: (DESACTIVATED)'),
                html.P('Unit is lice/fish'),
                dcc.Slider(
                    id={'type':'lice_slider','id':farm_data[name]['ID']},
                    step=0.05,
                    marks=marks_lice,
                    value=0.5,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=True,
                    )],
            width=8)]
    return farm_lay
    
def tab3_layout(All_names):
    return dbc.Card([
    dbc.CardHeader('Individual farm detail'),
    dbc.CardBody([
        dbc.Row([
            dcc.Dropdown(
            	id='dropdown_farms',
            	options=All_names,
            	searchable=True,
            	placeholder='Select a fish farm',
            ),
            dcc.Graph(
                id='progress-curves',
            ),    
        ]),
        dbc.Row(
            id='farm_layout',
            children=[]),
        
    ])
])



############# VARIABLES ##########################33
span=[0,2] # value extent
resolution=[50,100,200,400,800]
zooms=[9,8,7,6,5]
center_lat,center_lon=57.1, -6.4
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
rootdir='/data/'

if 'All_names' not in globals():
    print('loading dataset')

    master='data/westcoast_map_trim.zarr' #needs to go in the share drive
    super_ds=open_zarr(rootdir+master).drop('North Kilbrannan')  
    All_names=np.array(list(super_ds.keys()))
    ## remove border effects
    super_ds= super_ds.where(super_ds.x<-509600)


ref_biom=np.zeros(len(All_names))
    
if 'lice_data' not in globals():
    liceStore='data/consolidated_sealice_data_2017-2021.zarr'
    lice_data=open_zarr(rootdir+liceStore)
    ### mess in raw data
    id_c=250
    typos =['Fs0860', 'Fs1018', 'Fs1024'] #, 'FS1287 '
    correct=['FS0860', 'FS1018', 'FS1024']
    for mess, ok in zip(typos, correct):
        lice_data[ok].values[id_c]=lice_data[mess].values[id_c]
        lice_data=lice_data.drop(mess)
    
    
if 'farm_data' not in globals():
    csvfile='data/biomasses.csv'
    farm_data, times, tree, Ids =read_farm_data(rootdir+csvfile)
    print('Farm loaded')
    sepacsv= 'data/SEPA_GSID.csv'
    farm_data=add_new_SEPA_nb(rootdir+sepacsv)
    

###########  manage themes ###############

def mk_colorscale(cmp):
    '''
    format the colorscale for update in the callback
    '''
    idx =np.linspace(0,1,len(cmp))
    return np.vstack((idx, np.array(cmp))).T

def mk_template(template):
    '''
    Format the template for update in the callback
    '''
    fig=go.Figure()
    fig.update_layout(template=template)
    return fig['layout']['template']

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

app = dash.Dash(__name__,
                external_stylesheets=[url_theme1],#, dbc_css
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
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
        dcc.Store(id='my-store'),
    #header
        html.Div([
            html.H1('Visualisation of the Scottish Westcoast added sealice infestation'),
            ThemeSwitchAIO(aio_id='theme',
                    icons={"left": "fa fa-sun", "right": "fa fa-moon"},
                    themes=[url_theme1, url_theme2])
            ]),
    # Define tabs
        html.Div([
            dbc.Tabs(id='all_tabs',
                children= [
                dbc.Tab(tab1_layout(farm_data,center_lat, center_lon, span, cmp1, template_theme1),label='Interactive map',tab_id='tab-main',),
                #dbc.Tab(tab2_layout(farm_data, marks_biomass,marks_lice),label='Tuning dashboard',tab_id='tab-tunning',),
                dbc.Tab(tab3_layout(All_names),label='Farm data inspection',tab_id='tab-graph',),
                #dbc.Tab(tab4_layout(farm_data), label='All farms toggles', tab_id='tab-toggle'),
                ])
            ])
        ])
], fluid=True, className='dbc')


@cache.memoize()
def global_store(r):
    pathtods=f'data/map_{r}m.zarr'
    print('using global store ', pathtods)
    super_ds=open_zarr(rootdir+pathtods).drop('North Kilbrannan')
    ## remove border effects
    super_ds= super_ds.where(super_ds.x<-509600) 
    
    print('global store loaded')
    return super_ds



@app.callback(
    [Output({'type':'biomass_slider', 'id':MATCH}, 'disabled'),
    Output({'type':'lice_slider', 'id':MATCH}, 'disabled')],
    Input({'type':'switch', 'id':MATCH},'on'),
)
def desactivate_farms(switch):
    return not switch, not switch

@app.callback(
    Output('egg_toggle_output','children'),
    Input('egg_toggle','on')
)
def toggle_egg_models(eggs):
    if eggs:
        return 'Stien (2005)'
    else:
        return 'Rittenhouse et al. (2016)'

#@app.callback(
#    [Output({'type':'biomass_slider', 'id':ALL}, 'value'),
#    Output({'type':'lice_slider', 'id':ALL}, 'value')],
#    [Input('master_lice_slider', 'value'),
#    Input('master_biomass_slider','value')],
#    [State({'type':'biomass_slider', 'id':ALL},'value')]
#)
#def update_all_sliders(lice, biom, l):
#    Nb=len(l)
#    return (np.ones(Nb)*biom).tolist(), (np.ones(Nb)*lice).tolist()

@app.callback(
    [Output('heatmap', 'figure'),
    Output('heatmap_output', 'children'),
    Output('LED_biomass','value'),
    Output('LED_egg','value'),
    ],
    [#Input('submit_map','n_clicks'),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
    Input('power_streaming','on'),
    Input('heatmap', 'relayoutData'),
    Input('year_slider','value'),
    Input('biomass_knob','value'),
    Input('lice_knob','value'),
    Input('lice_meas_toggle','on'),
    Input('span-slider','value') ,
    ],
    [  
    State('power_streaming','on'),
    State('egg_toggle','on'),
    State({'type':'switch', 'id':ALL},'on'),
    #State({'type':'biomass_slider', 'id':ALL},'value'),
    #State({'type':'lice_slider', 'id':ALL},'value'),
    
    #State('resolution-slider','value'),
    State('heatmap', 'figure'),
    State('progress-curves','figure'),
    ]
)
def redraw( toggle,  power, relay,year, biomC, liceC, meas,  span,state_power, egg,  idx, fig, curves): 
    ctx = dash.callback_context
    
    ### toggle themes
    #if ctx.triggered[0]['prop_id'] == 'toggle.value':
    template = template_theme1 if toggle else template_theme2
    cmp= cmp1 if toggle else cmp2
    carto_style= carto_style1 if toggle else carto_style2
    
    # Scaling
    activated_farms= np.ones(len(All_names), dtype='bool')
    Coeff=np.ones(len(All_names)) 
    biomass_factor=np.ones(len(All_names))
    lice_factor=np.ones(len(All_names))/2
    if biomC ==0:
        biomC=0.00001
    if liceC==0:
        liceC=0.00001
    biomC /=100
    liceC *=2
    print('preparing lice factor')
    idx, biomass_factor, lice_factor, ref_biom=fetch_biomass(activated_farms, 
                                                     biomass_factor, lice_factor, year)
    # decide source lice data
    if meas:
        lice_factor=np.ones(len(All_names))/2*liceC
    name_list=np.array(list(farm_data.keys()))[idx] 
    
    ##### update discs farms
    current_biomass=[farm_data[farm]['reference biomass']*
                                           biomass_factor[farm_data[farm]['ID']] *biomC
                                           for farm in name_list]
    # print(current_biomass)
    fig['data'][1]=go.Scattermapbox(
                                lat=[farm_data[farm]['lat'] for farm in name_list],
                                lon=[farm_data[farm]['lon'] for farm in name_list],
                                text=name_list,
                                hovertemplate="<b>%{text}</b><br><br>" + \
                                        "Biomass: %{marker.size:.0f} tons<br>",
                                marker=dict(color='#62c462',
                                    size=current_biomass,
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    ),
                                name=f'Processed with biomass of may {year}')
                                
    fig['data'][0]['marker']['colorscale']=mk_colorscale(cmp)
    fig['data'][0]['marker']['cmax']=span[1]
    fig['data'][0]['marker']['cmin']=span[0]
    
    # modify egg model from Rittenhouse (16.9) to Stein (30)
    if egg:
        # lices *= 30/16.9
        c_lice=30/16.9
    else:
        c_lice=1
    # set global factor biomass x individual farm biom x individual lice x egg model
    Coeff=biomC*biomass_factor[idx]*lice_factor[idx]*c_lice    
    

    ### update heatmap
    if power: #ctx.triggered[0]['prop_id'] == 'power.on':
        fig['layout']['template']=mk_template(template)
        fig['layout']['mapbox']['style']=carto_style
             
        if idx.sum()>0:
            print('rasterizing map')
            ####
            # remove Achintraid because only NaN for some reason
            idx[0]=False
            ####

            if relay is not None:
                zoom=relay['mapbox.zoom']
            else:
                zoom=fig['layout']['mapbox']['zoom']
            r = select_zoom(zoom)
            print('zoom: ', zoom,' , resolution: ',r)
            super_ds=global_store(r)
            coordinates=get_coordinates(super_ds)

            fig['layout']['mapbox']['layers']=[
                                    {
                                        "below": 'traces',
                                        "sourcetype": "image",
                                        "source": mk_img(super_ds, name_list, span, Coeff,cmp),
                                        "coordinates": coordinates
                                    },
                                    ]
        else:
            # add a message?

            fig['layout']['mapbox']['layers']=[]
        relayed_zoom= zoom
    ## led values
    alllice=(Coeff*ref_biom[idx]).sum()*4.5*1000
    return fig, None, sum(current_biomass)*1000, int(alllice)


@app.callback([
    Output('progress-curves','figure'),
    Output('farm_layout','children'),
],
    Input(   'dropdown_farms', 'value',),
    State(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def farm_inspector(name, toggle):
    template = template_theme1 if toggle else template_theme2
    if not name:
        raise PreventUpdate
    else:
        curves=mk_farm_evo(name, times)
        curves['layout']['template']=mk_template(template)
        return curves, mk_farm_layout(name, marks_biomass,marks_lice)

@app.callback(
    Output('power_streaming','on'),
    Input('all_tabs', 'active_tab')
)
def update_control(tab):
   if not tab =='tab-main':
       return False

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True)
