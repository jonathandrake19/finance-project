import streamlit as st
import numpy as np
import Data_Downloader as dd
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
import Calculations as calc
import seaborn as sns
import yfinance as yf

#set up the page
st.title("Option PnL Calculator")
col1, col2 = st.columns(2)

st.sidebar.markdown('## Inputs ##')

#óption type determines how the BSE is solved and what initial user inputs are required
option_type = st.sidebar.selectbox('Option type', ['US', 'European'])

if option_type == 'European':
    V_0 = float(st.sidebar.text_input('Option purchase price: ', '0')) # price option was purchased for, determines PnL
    K = float(st.sidebar.text_input('Strike price: ', '0'))
    expiry = st.sidebar.text_input('Expiration date (yyyy-mm-dd): ', '')
    sigma_0 = float(st.sidebar.text_input('Volatility: ', '0'))
    S_0 = float(st.sidebar.text_input('Current asset price: ', '0'))

elif option_type == 'US': #downloads option data for stock from Yahoo finance as US options are commonly traded
    ticker = st.sidebar.text_input('Stock ticker: ', '')
    tk = yf.Ticker(ticker)
    S_0 = 0
    if ticker:
        S_0 = dd.current_price(ticker)
        st.write(f'Current stock price: ${round(S_0, 2)}')
        expiry = st.sidebar.selectbox('Expiration date: ', tk.options)

        calls, puts = dd.option_data(ticker, expiry)

        K = st.sidebar.selectbox('Strike price: ', calls['strike'])
        V_0 = float(st.sidebar.text_input('Price paid: ', '0'))
    
        sigma_0 = calc.implied_vol(ticker, 'uk', expiry)

#once inputs are recieved determine whether European or US and solve BSE to generate a price matrix
if S_0 and K and expiry and sigma_0:
    r = dd.risk_free_rate('uk', 30)/252
    T = datetime.strptime(expiry, '%Y-%m-%d').date()
    t = date.today()
    tau_0 = np.busday_count(t,T+timedelta(days=1))
    tau_vector = np.linspace(0, tau_0, tau_0+1)

    if option_type == 'European':
        #recieve user input to change the limits of the graph axes
        st.sidebar.header("Variables")
        S_range = st.sidebar.slider('Range for underlying price', min_value=50, max_value=300, value=(int(S_0)-10,int(S_0)+10),
                                 step=1, format='%d')
        S_vector = np.linspace(S_range[0], S_range[1], 10)

        sigma_range = st.sidebar.slider('Range for volatility', min_value=0.1, max_value=0.8,
                                     value=(0.5*sigma_0,1.5*sigma_0), step=0.01, format='%.2f')
        sigma_vector = np.linspace(sigma_range[0]/np.sqrt(252), sigma_range[1]/np.sqrt(252), 10)
        sigma_labels = sigma_vector*np.sqrt(252)

        #this input alows the user to generate graphs for each time step towards expiry
        t = st.sidebar.slider('Days from purchase', min_value=1, max_value=tau_0, value = 1, step = 1, format='%d')
        tau = tau_vector[-t]
        V_0_call = calc.european_call(S_0, K, tau_0, sigma_0/np.sqrt(252), r)

        x, y = np.meshgrid(S_vector, sigma_vector)

        V_matrix_calls = calc.european_call(x, K, tau, y, r)

        PnL_calls = V_matrix_calls - V_0

        #put-call parity to find V for puts
        difference = (K*np.exp(-r*tau_0) - S_0)
        V_0_put = V_0 + difference

        V_matrix_puts = calc.european_put(x, K, tau, y, r)

        PnL_puts = V_matrix_puts - V_0

        #scaling colourbar to ensure consistent colour (green for profit, red for loss)
        if abs(np.min(PnL_calls)) < np.max(PnL_calls):
            v_max = np.max(PnL_calls)
            v_min = v_max*-1
        else:
            v_min = np.min(PnL_calls)
            v_max = v_min*-1
            
        if abs(np.min(PnL_puts)) < np.max(PnL_puts):
            v_max_p = np.max(PnL_puts)
            v_min_p = v_max_p*-1
        else:
            v_min_p = np.min(PnL_puts)
            v_max_p = v_min_p*-1
        
        #plotting the heat maps
        fig_c, ax_c = plt.subplots(figsize=(8, 6))
        call_map = sns.heatmap(PnL_calls,
                            cmap='RdYlGn',
                            vmin= v_min,
                            vmax= v_max,
                            linewidths=0.5,
                            linecolor='k',
                            annot=True,
                            fmt = '.2f',
                            cbar=True,
                            cbar_kws={'label': 'PnL ($)'},
                            xticklabels= S_vector.round(0),
                            yticklabels= sigma_labels.round(2)
                            )
        ax_c.invert_yaxis()
        plt.xlabel('Stock price ($)')
        plt.ylabel('Volatility')

        fig_p, ax_p = plt.subplots(figsize=(8, 6))
        put_map = sns.heatmap(PnL_puts,
                            cmap='RdYlGn',
                            vmin= v_min_p,
                            vmax= v_max_p,
                            linewidths=0.5,
                            linecolor='k',
                            annot=True,
                            fmt = '.2f',
                            cbar=True,
                            cbar_kws={'label': 'PnL ($)'},
                            xticklabels= S_vector.round(0),
                            yticklabels= sigma_vector.round(2)
                            )
        ax_p.invert_yaxis()
        plt.xlabel('Stock price ($)')
        plt.ylabel('Volatility')

        with col1:
            st.markdown('### Call Option')
            st.write(f'Current fair price: ${round(V_0_call, 2)}')
            st.pyplot(fig_c)
        
        with col2:
            st.markdown('### Put Option')
            st.write(f'Current fair price: ${round(V_0_put, 2)}')
            st.pyplot(fig_p)

    if option_type == 'US':
        #calculate V matrix numerically and S and t vectors
        S, t, V_calls = calc.us_option(K, sigma_0/np.sqrt(252), tau_0, r/252, option_type='call')
        _, _, V_puts = calc.us_option(K, sigma_0/np.sqrt(252), tau_0, r/252, option_type='put')

        #current fair price calculation
        S_current = np.searchsorted(S, S_0)
        V_call_current = V_calls[S_current, 0]
        V_put_current = V_puts[S_current, 0]

        PnL_calls = V_calls - V_0
        PnL_puts = V_puts - V_0

        #user input for S and t to change graph limits
        st.sidebar.header("Variables")
        S_start = int(S_0) - 10
        S_end = int(S_0) + 10
        S_range = st.sidebar.slider('Underlying Asset Price: ', min_value=50, max_value=300, value=(S_start, S_end),
                                    step=1, format='%d')
        
        t_start = int(t[0])
        t_end = int(t[-1])
        t_range = st.sidebar.slider('Time to expiry: ', min_value=0, max_value=int(tau_0), value=(t_start, t_end),
                                    step=1, format='%d')
        
        #turning user selected range into the relevant indcies of the matrix
        S_index_lower = np .searchsorted(S, S_range[0])
        S_index_upper = np.searchsorted(S, S_range[1])
        
        t_index_lower = np .searchsorted(t[::-1], t_range[1])
        t_index_upper = np.searchsorted(t[::-1], t_range[0])

        #to maintain a a 10x10 heatmap
        delta_S = S_index_upper - S_index_lower
        if delta_S < 10:  
            S_end = int(S[S_index_upper + delta_S])
            S_index_upper = np.searchsorted(S, S_end)
            S_index_range = np.linspace(S_index_lower, S_index_upper, 10, dtype=int)
        
        if delta_S >= 10:
            S_index_range = np.linspace(S_index_lower, S_index_upper, 10, dtype=int)

        delta_t = t_index_lower - t_index_upper
        if delta_t < 10:
            t_end = int(t[t_index_upper + delta_t])
            t_index_upper = np.searchsorted(t, t_end)
            t_index_range = np.linspace(t_index_lower, t_index_upper, 10, dtype=int)

        if delta_t >= 10:
            t_index_range = np.linspace(t_index_lower, t_index_upper, 10, dtype=int)
        
        
        #create a 10x10 submatrix to show the ranges selected by the user
        calls_subset = PnL_calls[np.ix_(S_index_range, t_index_range)]
        puts_subset = PnL_puts[np.ix_(S_index_range, t_index_range)]

        #setting up axes labels to correspond to actual values of S and t
        S_labels = np.linspace(S[S_index_range[0]], S[S_index_range[-1]], 10)
        t_labels = np.linspace(t[t_index_range[0]], t[t_index_range[-1]], 10)

        #scaling the colourbar to ensure consistant colour (green for profit, red for loss)
        if abs(np.min(calls_subset)) < np.max(calls_subset):
            v_max = np.max(calls_subset)
            v_min = v_max*-1
        else:
            v_min = np.min(calls_subset)
            v_max = v_min*-1
            
        if abs(np.min(puts_subset)) < np.max(puts_subset):
            v_max_p = np.max(puts_subset)
            v_min_p = v_max_p*-1
        else:
            v_min_p = np.min(puts_subset)
            v_max_p = v_min_p*-1

        #plotting heatmaps
        fig_c, ax_c = plt.subplots(figsize=(8, 6))
        call_map = sns.heatmap(calls_subset,
                            cmap='RdYlGn',
                            vmin= v_min,
                            vmax= v_max,
                            linewidths=0.5,
                            linecolor='k',
                            annot=True,
                            fmt = '.2f',
                            cbar=True,
                            cbar_kws={'label': 'PnL ($)'},
                            yticklabels= S_labels.round(2),
                            xticklabels= t_labels.round(2)
                            )
        ax_c.invert_yaxis()
        plt.xlabel('Time to maturity (days)')
        plt.ylabel('Stock price ($)')

        fig_p, ax_p = plt.subplots(figsize=(8, 6))
        put_map = sns.heatmap(puts_subset,
                            cmap='RdYlGn',
                            vmin= v_min_p,
                            vmax= v_max_p,
                            linewidths=0.5,
                            linecolor='k',
                            annot=True,
                            fmt = '.2f',
                            cbar=True,
                            cbar_kws={'label': 'PnL ($)'},
                            yticklabels= S_labels.round(2),
                            xticklabels= t_labels.round(2)
                            )
        ax_p.invert_yaxis()
        plt.xlabel('Time to maturity (days)')
        plt.ylabel('Stock price ($)')
        
        with col1:
            st.markdown('### Call Option ###')
            st.write(f'Current fair price: ${round(V_call_current, 2)}')
            st.pyplot(fig_c)

        with col2:
            st.markdown('### Put Option ###')
            st.write(f'Current fair price: ${round(V_put_current, 2)}')
            st.pyplot(fig_p)

else:
    st.markdown('### Input your info ###')