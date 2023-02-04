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
    return dbc.Row([
                dbc.Col([
                    dbc.CardLink('Developped for the Coastal Community Network', 
                        href="https://www.communitiesforseas.scot"),
                    dbc.CardLink('contact', href="mailto:julien.moreau@nw-edge.org")]),
                dbc.Col([
                    html.P('Copyright 2022-3'),
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
                        #colorscale=mk_colorscale(fire),
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
                height=512,
                width=1024,
                hovermode='closest',
                showlegend=False,
                margin=dict(b=3, t=5),
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
    logger.info('figure done.')
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
                        ),
                    dbc.Tooltip(''' 
                        Decrease or increase all the fish farm biomasses.''',target='biomass_knob'),
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
                        Infestations of 8 have been reported (cf. farm inspection tab)''',target='biomass_knob'),
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

def mk_map_pres(): #
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader('Compute a new density map'),
                dbc.CardBody([
                    html.Div(
                        [dbc.Button('Update density map',
                            id='trigger', 
                            n_clicks=0),],
                        className="d-grid gap-2 d-md-flex justify-content-md-center",
                        ),
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
                    ])
                ]),
            dbc.Card([
                dbc.CardHeader('Select the contributors to the map'),
                dbc.CardBody([
                    daq.BooleanSwitch(id='existing_farms_toggle', 
                        on=True,
                        label='Existing farms'),
                    dbc.Tooltip('Activate this toggle to visualise the lice density from existing farms',
                        target='existing_farms_toggle'),
                    daq.BooleanSwitch(id='future_farms_toggle',
                        on=False,
                        label='Planned farms'),
                    dbc.Tooltip('''Activate this toggle to visualise the lice density from planned farms. 
                                You also have to decide which of these farms to include in the dataset.''',
                        target='future_farms_toggle'),
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
                                        ),]),
                                    dbc.Tooltip('''Choose which egg production model suits best. 
                                                Rittenhouse et al. based on experimental data, 
                                                produced an equation that suggested 16 eggs released per hour per adult copepodid. 
                                                Stein 2005, based on model matching of real data suggest 30 eggs /hour.''', 
                                        target= 'egg_toggle',
                                        placement='bottom'),
                                ])
                            )
                        ])
            ],width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader('Select the planned farms to include'),
                dbc.CardBody([
                    html.H5("Planned farms appear as blue bubbles"),
                    dcc.Checklist(
                                id='planned_checklist',
                                # options=future_farms['Name'],
                                inline=False,
                                labelStyle={'display': 'block'},
                                ),     
                      ]),
                 ]),
            dbc.Card([
                dbc.CardHeader('Selected Farm'),
                dbc.CardBody([
                    html.Div([
                        html.P(id='name_farm'),
                        dbc.Button('Inspect farm data',
                               id='inspect-button', 
                               n_clicks=0),],
                        className="d-grid gap-2 d-md-flex justify-content-md-center",
                        ),
                    dbc.Tooltip('''
                        Inspect the active farm you selected on the map''',
                        target='inspect-button'),
                    ]),
                ]),
            ],width=3),
        dbc.Col([
            tuning_card()
        ],width=6),
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
                dbc.Col([
                    dcc.Graph(
                        id='heatmap',
                        figure=init_the_figure()
                        ),
                    dcc.Loading(
                        id='figure_loading',
                        children=[html.Div(id='heatmap_output'),],
                        type='graph',
                        fullscreen=True
                        ),
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
                                max=10,
                                step=0.25,
                                marks={n:'%s' %n for n in range(11)},
                                value=[0,0.75],
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
    #fig_p.update_layout(
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
    		    dbc.Row(
                	daq.BooleanSwitch(
                 	   id={'type':'switch','id':data['ID']},
                	    on=True,
                	    label="Toggle farm on/off",
                	    labelPosition="top"
                	    )),

              	     dbc.Row([
              	          html.P('Site identification number (GSID): '+data['GSID']),
              	          html.P('SEPA Reference: ' + data['Site ID SEPA']),
              	          html.P('Marine Scotland Reference: ' + data['Site ID Scot env']),
              	          html.P('Marine Scotland site name: ' + data['Name MS']),
              	          #html.P('Production Year: '+ data['Prod year']),
              	          html.P('Operator: ' + data['operator']),
              	          ]),
                   ], width=3),
            dbc.Col([
                html.H3('Modelled Peak Biomass {} tons'.format(data['reference biomass'])),
                html.H3('Average lice per fish {}'.format(np.round(data['mean lice'],2))),
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
                    )],
            width=8)]
    return farm_lay
    
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
    return [
     dcc.Textarea(id='logs', style={'width':'100%','height':300}),
     dcc.Interval(id='interval')]

logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('sealice_logger')
logger.setLevel(logging.DEBUG)
