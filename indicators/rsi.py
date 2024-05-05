# Calculates the RSI for an asset - expects single df column of historical closes (Series) 
def calculate_rsi(data, period, backtest):
        # Calculate the change between all current and prev periods and add to series
        delta = data.diff()
        delta = delta[1:]
        
        # Create a series for gains and a series for losses, sub 0 when relevant
        gain = delta.where(delta > 0, 0)
        loss = -1*delta.where(delta < 0, 0)
        
        # Calculate moving averages for gains and losses
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        
        # Apply Wilder smoothing formula for better accuracy
        for i in range(1, len(data) - period):
            avg_gain.iloc[i + period - 1] = (avg_gain.iloc[i + period - 2] * 13 + gain.iloc[i + 13]) / period
            avg_loss.iloc[i + period - 1] = (avg_loss.iloc[i + period - 2] * 13 + loss.iloc[i + 13]) / period
        
        # Calculate relative strength
        rs = (avg_gain/avg_loss)
        
        # Calculate relative strength index
        rsi = 100 - (100/(1 + rs)) 
        
        rsi = rsi.round(1)
        
        if backtest == True:
            return rsi
        else:
            return rsi.iloc[-1]