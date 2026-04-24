import requests
import pandas as pd

BASE_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://api-gcp.binance.com/api/v3/klines",
    "https://api1.binance.com/api/v3/klines",
    "https://api2.binance.com/api/v3/klines",
    "https://api3.binance.com/api/v3/klines",
    "https://api4.binance.com/api/v3/klines",
]

def get_binance_klines(symbol="BTCUSDT", interval="1h", limit=200):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    last_error = None

    for base_url in BASE_URLS:
        try:
            print(f"Trying: {base_url}")
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            columns = [
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
            ]

            df = pd.DataFrame(data, columns=columns)
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

            numeric_cols = [
                "open", "high", "low", "close", "volume",
                "quote_asset_volume", "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume"
            ]
            for col in numeric_cols:
                df[col] = df[col].astype(float)

            df["number_of_trades"] = df["number_of_trades"].astype(int)
            return df

        except Exception as e:
            print(f"Failed on {base_url}: {e}")
            last_error = e

    raise RuntimeError(f"All Binance endpoints failed. Last error: {last_error}")


if __name__ == "__main__":
    btc_1h = get_binance_klines(symbol="BTCUSDT", interval="1h", limit=200)
    print(btc_1h[["open_time", "open", "high", "low", "close", "volume"]].head())