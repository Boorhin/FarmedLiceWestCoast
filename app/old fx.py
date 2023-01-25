
@app.callback(
    [Output({'type':'biomass_slider', 'id':MATCH}, 'disabled'),
    Output({'type':'lice_slider', 'id':MATCH}, 'disabled')],
    Input({'type':'switch', 'id':MATCH},'on'),
    #log=True
)
def desactivate_farms(switch):
    #dash_logger.info('Farm switched off')
    return not switch, not switch



@app.callback(
    ServersideOutput('fig_store','data'),
    # Output('heatmap','figure'),
    Input('init','data'),
    log = True
)
def init_the_figure(variables, dash_logger: DashLogger):
    logger.info('Making figure ...')
    dash_logger.info('Building map')
    variables=variables[0]
    span=[0,0.75]
    center_lat, center_lon=57.1, -6.4
    # variables=json.loads(init)
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorscale=fire,
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
                                lat=[variables['farm_data'][farm]['lat'] for farm in variables['farm_data'].keys()],
                                lon=[variables['farm_data'][farm]['lon'] for farm in variables['farm_data'].keys()],
                                text=[farm for farm in variables['farm_data'].keys()],
                                marker=dict(color='#e9ecef', size=4, showscale=False),
                                name='Mapped farms'))
    fig.add_trace(go.Scattermapbox(
                                lat=variables['future_farms']['Lat'],
                                lon=variables['future_farms']['Lon'],
                                text=variables['future_farms']['Name'],
                                hovertemplate="<b>%{text}</b><br><br>" + \
                                        "Biomass: %{marker.size:.0f} tons<br>",
                                marker=dict(color='#00ccff',
                                    size=variables['future_farms']['Biomass_tonnes'],
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
                #mapbox=dict(
                #    bearing=0,
                #    center=dict(
                #        lat=center_lat,
                #        lon=center_lon,
                #    ),
                #    pitch=0,
                #    zoom=5.5,
                #    style="carto-darkmatter",
                #    )
                    )
    logger.info('figure done.')
    return [fig]# , fig   
