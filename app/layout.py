import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc as dcc
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Output, Input, html, State, MATCH, ALL, DashProxy, LogTransform, DashLogger
import dash_daq as daq
import logging, random
import numpy as np
from datetime import datetime, timedelta
from colorcet import fire
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template

###########  manage themes ###############

def mk_colorscale(cmp):
    '''
    format the colorscale for update in the callback
    '''
    idx =np.linspace(0,1,len(cmp))
    return np.vstack((idx, np.array(cmp))).T.tolist()

def mk_template(template):
    '''
    Format the template for update in the callback
    '''
    fig=go.Figure()
    fig.update_layout(template=template)
    return fig['layout']['template']
    
    
#### manage main card ###############

def main_header():
    '''
    Define the main header of the app'''
    url_theme1=dbc.themes.SLATE
    url_theme2=dbc.themes.SANDSTONE
    return [html.Img(src='assets/logo.svg',
                     width=96,
                     alt='logo',
                     style={'float':'right', 'padding':'5px'},
                     className='logo'),          
            html.H1('Scottish Westcoast artificial sealice infestation'),
            ThemeSwitchAIO(aio_id='theme',
                    icons={"left": "fa fa-sun", "right": "fa fa-moon"},
                    themes=[url_theme1, url_theme2])
            ]

def main_footer():
    '''
    Define the main footer of the app'''
    with open('assets/build-date.txt') as f:
         date=f.readline()
    return dbc.Row([
                dbc.Col([
                    dbc.CardLink('Developped for the Coastal Community Network', 
                        href="https://www.communitiesforseas.scot"),
                    dbc.CardLink('contact', href="mailto:julien.moreau@nw-edge.org")]),
                dbc.Col([
                    html.P('Copyright 2022-3'),
                    html.P(f'Latest build {date}'),
                    dbc.CardLink('source code', href="https://github.com/Boorhin/FarmedLiceWestCoast"),
                    ]),
                dbc.Col([
                    dbc.CardLink('Hosted by JASMIN', href="https://jasmin.ac.uk/"),
                    html.Img(src='assets/jasmin_logo.png')
                    ]),
                ],justify='center', align='center')
 
#####################TAB 1 ###########################

def init_the_figure():
    logger.info('Making figure ...')
    span=[0,0.75]
    center_lat, center_lon=57.1, -6.4
    # variables=json.loads(init)
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorbar=dict( 
                            title= dict( 
                                text="copepodid/m²/day", #r'$copepodid.m^{-2}.day^{-1}$',
                                side='right'
                                ), 
                            orientation='v', # style={'writing-mode':'vertical-rl'},
                            ),
                        cmax=span[1],
                        cmin=span[0],
                        showscale=True,
                        ),
                    name='only_scale',
                    showlegend=False),)
    fig.add_trace(go.Scattermapbox(lat=[None],
                                lon=[None],
                                marker=dict(color='#62c462',
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    ),
                                name=f"Processed with biomass of may {2021}"))
    fig.add_trace(go.Scattermapbox(
                                lat=[None],
                                lon=[None],
                                text=[None],
                                marker=dict(color='#e9ecef', size=4, showscale=False),
                                name='Mapped farms'))
    fig.add_trace(go.Scattermapbox(
                                lat=[None],
                                lon=[None],
                                text=[None],
                                hovertemplate="<b>%{text}</b><br><br>" + \
                                        "Biomass: %{marker.size:.0f} tons<br>",
                                marker=dict(color='#00ccff',
                                    #size=[None],
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    ),
                                name='Planned farms'))

    fig.update_layout(
                #height=512,
                hovermode='closest',
                showlegend=False,
                margin=dict(b=1, t=1, l=0, r=0.1),
                # template=template,
                mapbox=dict(
                    bearing=0,
                    center=dict(
                        lat=center_lat,
                        lon=center_lon,
                    ),
                    pitch=0,
                    zoom=5.5,
                    style="carto-darkmatter",
                    )
                    )
    logger.info('figure done.')
    return fig
    
def make_base_figure(farm_data, center_lat, center_lon, span, cmp, template):
    logger.info('Making figure ...')
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorscale=cmp,
                        cmax=span[1],
                        cmin=span[0],
                        showscale=True,
                        ),
                    name='only_scale',
                    showlegend=False),)
    fig.add_trace(go.Scattermapbox(lat=[0],
                                lon=[0],
                                ))
    fig.add_trace(go.Scattermapbox(
                                lat=[farm_data[farm]['lat'] for farm in farm_data.keys()],
                                lon=[farm_data[farm]['lon'] for farm in farm_data.keys()],
                                text=[farm for farm in farm_data.keys()],
                                marker=dict(color='#e9ecef', size=4, showscale=False),
                                name='Mapped farms'))
    fig.add_trace(go.Scattermapbox(
                                lat=future_farms['Lat'],
                                lon=future_farms['Lon'],
                                text=future_farms['Name'],
                                hovertemplate="<b>%{text}</b><br><br>" + \
                                        "Biomass: %{marker.size:.0f} tons<br>",
                                marker=dict(color='#00ccff',
                                    size=future_farms['Biomass_tonnes'],
                                    sizemode='area',
                                    sizeref=10,
                                    showscale=False,
                                    ),
                                name='Planned farms'))

    fig.update_layout(
                height=512,
                # width=1024,
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
    logger.info('figure done.')
    return fig

def tuning_card():
    return dbc.Card([
        
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
                        ),
                    dbc.Tooltip(''' 
                        Decrease or increase all the fish farm biomasses.''',target='biomass_knob'),

                    daq.BooleanSwitch(
                                        id='egg_toggle',
                                        on=True,
                                        label='Nauplii production model',
                                        ),
                    html.P(
                                        id='egg_toggle_output',
                                        style={'text-align':'center'}
                                        ),
                    dbc.Tooltip('''Choose an egg hatching model suits best. 
                                        Rittenhouse et al. based on experimental data, 
                                        produced an equation that suggested 16 eggs released per hour per adult copepodid. 
                                        Stien et al. 2005, based on model matching of real data suggest 30 eggs /hour.''', 
                                        target= 'egg_toggle',
                                        placement='bottom'),          
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
                        ),
                    dbc.Tooltip(''' 
                        Decrease or increase the infestation rates for all the farms. 
                        The good practice is to maintain at 0.5 louse/fish. 
                        Infestations of 8 have been reported (cf. farm inspection tab)''',target='lice_knob'),
                    daq.BooleanSwitch(
                         id='lice_meas_toggle',
                         label='Use and extrapolate reported lice',
                         on=False
                         ),
                    dbc.Tooltip('''Very little data are available on lice infestation. 
                    This algorithm will first try to find if there are data in the May season you selected. 
                    If there isn't it will try to make an average of recorded lice for the farm. 
                    If the farm never reported lice counts then it will use the nearest farm that has data.''',
                    target='lice_meas_toggle'
                    )
                    ]),
                ])
            ])
        ])

def mk_modal(origin, is_open):
   txt=''
   if "no toggle" in origin:
       txt="Select at least one of the toggle from existing or planned farms.\n"
   if "no future" in origin:
       txt += "At least one planned farm needs to be selected"
   modal= dbc.Modal([
       dbc.ModalHeader(dbc.ModalTitle('No farm selected')),
       dbc.ModalBody(txt)],
       id="modal_checklist",
       is_open=is_open)
   return modal

def select_contributors():
    return dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                    dbc.Col([
                        daq.BooleanSwitch(id='existing_farms_toggle', 
                            on=True,
                            label='Existing farms  (green bubbles)'),
                        dbc.Tooltip('Activate this toggle to visualise the lice density from existing farms',
                            target='existing_farms_toggle'),
                        daq.BooleanSwitch(id='future_farms_toggle',
                            on=False,
                            label='Planned farms  (blue bubbles)'),
                        dbc.Tooltip('''Activate this toggle to visualise the lice density from planned farms. 
                                You also have to decide which of these farms to include in the dataset.''',
                            target='future_farms_toggle'),
                         ]),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Select planned farms to include"),
                            dbc.CardBody([
                                dcc.Checklist(
                                    id='planned_checklist',
                                # options=future_farms['Name'],
                                    inline=False,
                                    labelStyle={'display': 'block'},
                                    ),
                                ]),
                            ])
                        
                        ],),
                        ])
                    ]),
                ]),

def mk_map_pres(): #
    return dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Button("Select the contributors to the map",
                    id="collapse_button_select_contributor",
                    n_clicks=0),
                dbc.Collapse(
                    select_contributors(),
                    id="collapse_select_contributor",
                    is_open=False,
                    ),
                ], className="d-grid gap-2 col-12 mx-auto")
            
            
            ],md=6, xs= 11),
        
        dbc.Col([
            html.Div([
                dbc.Button('Adjust biomass and lice infestation',
                    id="collapse_button_tune",
                    n_clicks=0),
                dbc.Collapse(
                    tuning_card(),
                    id="collapse_tune",
                    is_open=False,
                    ),
                ], className="d-grid gap-2 col-12 mx-auto")
            
        ],md=6, xs=11),
    ]),

def tab1_layout():
    return dbc.Card([
    dbc.CardHeader('Control dashboard'),
    dbc.CardBody([
        dbc.Card([
            dbc.CardBody(mk_map_pres())
        ]),
        dbc.Card([
            dbc.CardBody([
            dbc.Row([
                    dcc.Graph(
                        id='heatmap',
                        figure=init_the_figure(),
                        #mathjax=True,
                        ),
                    dcc.Loading(
                        id='figure_loading',
                        children=[html.Div(id='heatmap_output'),],
                        type='graph',
                        fullscreen=True
                        ),
                ]),
            dbc.Row([
                dbc.Col([
                    html.Div(
                        [dbc.Button('',
                            id='trigger', 
                            n_clicks=0),
                    dbc.Tooltip('''
                        This updates or creates the lice density map according to the parameter you have selected. 
                        You can simulate a global change of the farm biomasses, the global lice infestation levels, 
                        use the reported lice from the best data we have and scale the color range. 
                        The map you produce will depend of the area visible in the map and the level of zoom. 
                        The resolution available are 800-400-200-100-50 and will change automatically according 
                        to the zoom in the viewport. If you change a parameter, you will have to press this button 
                        to see the change. Be patient as this involves very heavy computations and can take a while to refresh. 
                        ''',
                        target = 'trigger'),
                        dbc.Button('Select a farm on the map for inspection',
                               id='inspect-button', 
                               n_clicks=0,
                               disabled=True),],
                        className="d-grid gap-2 col-11 mx-auto",
                        ),
                    dbc.Tooltip('''
                        Inspect the active farm you selected on the map''',
                        target='inspect-button'),        
                    ], xs= 11, md=3),
                dbc.Col([
                    dcc.Markdown(r'Colormap range in $copepodid.m^{-2}.day^{-1}$',
                    mathjax=True),
                    dcc.RangeSlider(
                                id='span-slider',
                                min=0,
                                max=10,
                                step=0.25,
                                marks={n:'%s' %n for n in range(11)},
                                value=[0,0.75],
                                vertical=False,
                                )
                    ], xs= 12,md=9),
                ], align='center'),
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
                    dbc.Tooltip('''Select the year of production ''', 
                                        target= 'year_slider',
                                        placement='bottom')
                ]),
                dbc.Row([
                    dbc.Col([
                        daq.LEDDisplay(
                            id='LED_biomass',
                            label='Total fish farmed in may (tons)',
                            color='#f89406',
                            backgroundColor='#7a8288',
                            ),
                        ]),
                    dbc.Col([
                        daq.LEDDisplay(
                            id='LED_egg',
                            label='Hourly release of sealice nauplii from fish farms',
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
def convert_dates(numpy_date):
    unix_epoch = np.datetime64(0, 's')
    one_second = np.timedelta64(1, 's')
    return datetime.utcfromtimestamp((numpy_date-unix_epoch)/ one_second)
    
    
def init_farm_plot():
    '''
    Initialise the curve plot for individual farms
    '''
    fig_p = make_subplots(specs=[[{"secondary_y": True}]])
    fig_p.add_trace(go.Scatter(
           x=[None],
           y=[None],
           mode='lines+markers',
           name='Biomass'),
           secondary_y= False)
    fig_p.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='lines+markers',
        name='lice record',
        ),
        secondary_y= True)
    fig_p.add_trace(go.Scatter(x=[None],
                               y=[None],
                               mode='lines',
                               line=dict(color='#f89406', dash='dash'),
                               name='modelled lice infestation'), 
                               secondary_y= True)
    fig_p.add_trace(go.Scatter(x=[None],
                               y=[None],
                               mode='lines',
                               line=dict(color='firebrick', dash='dash'),
                               name='Average lice infestation'),
                               secondary_y= True)
    for y in range(2003,2022):
        fig_p.add_vrect(x0=datetime(year=y, month=5, day=1),x1=datetime(year=y, month=6, day=1),line=dict(width=0), fillcolor="green", opacity=0.7)
        #fig_p.add_vline(x=datetime(year=y, month=5, day=1), line=dict(color='green', dash='dash'))
    fig_p.update_yaxes(title='Recorded fish farmbiomass (tons)',
                    showgrid=False, secondary_y=False)
    fig_p.update_yaxes(title='Reported average lice/fish',
                    showgrid=False, secondary_y=True)                
    fig_p.update_layout(
        legend=dict(orientation='h'),
        )
    
        #margin=dict(b=15, l=15, r=5, t=5),
        #template=mk_template(template)
    #    )
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
    
def mk_farm_layout(name, marks_biomass,marks_lice, data):
    farm_lay= [dbc.Col([
              	          html.P('Site identification number (GSID): '+data['GSID']),
              	          html.P('SEPA Reference: ' + data['Site ID SEPA']),
              	          html.P('Marine Scotland Reference: ' + data['Site ID Scot env']),
              	          html.P('Marine Scotland site name: ' + data['Name MS']),
              	          #html.P('Production Year: '+ data['Prod year']),
              	          html.P('Operator: ' + data['operator']),
                   ], md=3, xs=12),
            dbc.Col([
                html.H3('Modelled Peak Biomass {} tons'.format(data['reference biomass'])),
                html.H3('Average lice per fish {}'.format(np.round(data['mean lice'],2))),
            ],md=8, xs=12)
            ]
    return farm_lay

def microtuning(data):

    layout= [
    dbc.Row(
                	daq.BooleanSwitch(
                 	   id={'type':'switch','id':data['ID']},
                	    on=True,
                	    label="Toggle farm on/off",
                	    labelPosition="top"
                	    )),
     html.H3('Tune Farm biomass: (DESACTIVATED)'),
                dcc.Slider(
                    id={'type':'biomass_slider','id':data['ID']},
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
                    id={'type':'lice_slider','id':data['ID']},
                    step=0.05,
                    marks=marks_lice,
                    value=0.5,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=True,
                    ),]
    return layout
    
def tab3_layout():
    return dbc.Card([
    dbc.CardHeader('Individual farm detail'),
    dbc.CardBody([
        dbc.Row([
            dcc.Dropdown(
            	id='dropdown_farms',
            	options=[],
            	searchable=True,
            	placeholder='Select a fish farm',
            ),
            dcc.Graph(
                id='progress-curves',
                figure=init_farm_plot()
            ),    
        ]),
        dbc.Row(
            id='farm_layout',
            children=[]),
        
    ])
])

##################### TAB4 #############################3


def tab4_layout():
    doc= dbc.Card([
       #dbc.CardHeader('General concepts'),
       dbc.CardBody([
           dcc. Markdown('''
This app aims at illustrating the cumulative impact of present and future fish farms on the artificial production of salmon lice (*Lepeophtheirus salmonis*) over the area of the West Coast of Scotland. This work is made with the best of our knowledge on current research in biological and hydrodynamic modelling regarding artificial infestation of salmon lice. Salmon lice are arthropods infesting fish farms, attaching to, feeding and killing salmonids contained in open water cages. When fully developped, these parasites grow strings of eggs while they are attached to their host. When the eggs hatch, the larvae (Nauplii) get transported by the currents and dispersed in the ocean. These larvae grow up into an infective larvae, the copepodid, that will attach to other hosts and grow up into a new generation of adults either in the cages or in the wild. In the app, we summarise where the copepodid accumulate in the ocean according to different scenario and models. This allows to assess the situation regarding the current and future infestation levels and if wild salmonids are ill-affected by the release of the parasites from the aquaculture industry.

#### Oceanographic model
The oceanographic model that drives the dispersion of the salmon lice is based on the work of Dr Tom Scanlon at MTS-CFD. The hydrodynamic model is tridimensional and has been constructed thanks to Telemac 3D. The model domain extends from the Mull of Kintyre in the South to Whitten Head in the North and includes all main islands off the West Coast. The computational mesh was constructed using a flexible mesh approach with a varying spatial resolution down to tens of metres at river inlets. The oceanography of the Scottish West Coast is an area of complex water circulation exhibiting various levels of density stratification throughout the year. The capture of such 3D phenomena necessitates that a 3D, non-hydrostatic approach is used. Freshwater sources from local rivers discharge were included, allowing to model salinity and temperature differences that act as an important driving force for fluid movement in this fjordic systems. The influence of meteorological wind forcing on the modelled current speeds was included for the time of year of the study. Coriolis force for Earth spin was also included in the model. The hydrodynamic model was validated against published observed hydrographic data (water levels and currents) from around the West Coast. This included the long-term tide gauges operated by the British Oceanographic Data Centre (BODC). The model correctly simulates the propagation of the tide over the West Coast, with a satisfactory validation against observed water levels at different locations. It was also found that the 3D HD model provides a reasonable description of the flow currents around the West Coast in terms of the current magnitudes, directions, salinity and temperature levels.
This model offers general insight into the spatial and temporal variation in the flow environment around the West Coast of Scotland. The hydrodynamic model provides a suitable basis for modelling salmon lice impact on wild salmon and sea trout and an assessment of both the near-field and far-field (regional/dispersion) effects compensating for the absence of direct field measurements.

#### Salmon-lice model
The salmon-lice model has been developped by Dr Julien Moreau (NW-Edge) and integrated in the particle tracking software OpenDrift from the Meteorological Institute of Norway. The use of hydrodynamic modelling to predict salmon lice densities and the risk presented to wild salmonids is common, particularly in Norway. Marine Scotland and SEPA are working on similar projects in Scotland. The integrated biological model draws on the methods and assumptions used by Scottish and Norwegian modellers working for government agencies, as well as other peer-reviewed research.The hydrodynamic model produces flow currents for the Lagrangian transport of salmon lice “particles”. Each particle may be thought of as representing a “packet” or “super-individual” of salmon lice. Particles are introduced at -5m at the location of fish farms across the West Coast of Scotland. Each hour 50 such particle is released in each farms for the duration of the experiment. Each super-individual released contains nauplii only. The number of nauplii is directly the result of the biomass of the farm, the average infestation and egg model, i.e. the number of egg an adult female louse can produce per hour. The super-individual population then evolve through time, nauplii become progressively infective copepodid, there is a constant mortality rate. The particle is active until the last copepodid in it, dies.
Once the model has been run, the number of copepodid in each particle through the whole experiment are projected into a grid to form a density map. Such as the ones you can generate in the app. The reason density maps are used is that the density of copepodid per m² per day is used to assess potential harm to wild migrating salmon. SEPA considers that 0.75 copepodid/m² is harmful to salmon smolt migrating on the first day, on the second day 0.375 is harmful, 0.25 the third one, etc. According to tracking data, a smolt can take 16 days to cross the area from East to West, which would imply theoretically that the average infestation rate should be under 0.75/16 days = c.0.05 copepodid/m²/d. 

#### What you can do with the app
  * You can change the theme from the default dark that is energy and eyesight saving to the clear one which is more suitable for printing. 
  * You can locate and inspect reported fish farm data. The white dots represent fish farms that have been active on the West Coast. If you select one of these, you will have the name of the farm that you can then investigate with the button **inspect farm data**. This will bring you to the second tab where you can visualise the biomass evolution and the reported sealice numbers. Other additional information are also available there. Such as the operator and the different identification numbers we could gather.
  * You can control the biomass of each farm by selecting the year of production. We use reported salmon farms biomass to scale the super-individuals. When you use the year slider, you will see the green bubbles on the map change size because the area of these bubbles is proportional to the biomass reported in May of that year.
  * You can visualise the planned fish farms, their location and their relative biomass compared to the existing farms. They are represented in blue. You cannot inspect them.
  * You can visualise the global biomass farmed during the year you select as well as the number of sealice produced each day by the aquaculture industry in May that year.
  * You can visualise the effects of globally increasing the fish farm biomass. The Scottish government has announced they wanted to double it. You can put it to 200%. You can also look at what biomass would reduce significantly the risk at the scale of the West coast by reducing the % of biomass.
  * You can tune the infestation rates (lice per fish). The good practice standards are of 0.5 lice per farmed fish. It you look at the reported infestation rates, you will see that it could be much higher during outbreaks. You can actually toggle the switch **Use and Extrapolate reported lice** that will try to find reported lice numbers for the may of the year you select. If it fails, it will take the average lice infestation for that farm and if the farm has never reported, it will take 0.5 as a default value.
  * You can change the egg production model, meaning the number of nauplii produced per hour by each louse. Most modellers use the work of Stien et al. (2005) but Rittenhouse et al. (2016) is an alternative one you can test too.
  * You can add the contribution to the density maps of planned farms based on their declared max biomass and a standard lice density of 0.5 (except if you modify the global infestation levels).
  * You can change the resolution of the map you display. The map resolution varies as a function of the viewport from 800m to 50m. To limit the resource used, only the area visible in the map viewport is rendered. To visualise another area, you will have to press the **Render density map** again. When you browse the map, notifications will indicate the resolution you would have if you compute the map.
  * You can generate density maps with the button **Render density map** this will take into account the parameters aforementioned. If you change, the year, the global biomass, the global lice infestation, the wiewport or try to use reported biomass you will need to refresh the map to see the updated parameters.
  * You can save a screenshot of the map with the button appearing in the upper-right of the map **Download plot as png**.
  ![Make a screenshot](assets/screenshoting.png)
  
#### Known limitations
  * Internet connections with poor ping will struggle to display the maps and can be timed out.
  * Small screens will struggle to display the app, try to look at it in a landscape if you have to watch it on a low-resolution screen. This is mostly made as an office app and is not mobile friendly for now.
  * If you zoom in too much the amount of data generated and encrypted will be very large. This might not be suitable if your connection is poor or if there are a lot of simultaneous users. We are graciously hosted and there isn't unlimited resources available for the app.
  * This is a relatively complex system with potentially bugs, so please report them through the contact link (email).
  * Sometimes, navigating between tab shows the map viewport not fully resolved. If you change slightly the browser window size or zoom, it will render properly.

'''),
          
           ]),
       ])
    return doc

logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('sealice_logger')
logger.setLevel(logging.DEBUG)
