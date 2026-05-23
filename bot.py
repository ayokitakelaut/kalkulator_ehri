import os
import sys
import requests
import gate_api

# -----------------------------------------------------------------------------
# KONFIGURASI UTAMA BOT
# -----------------------------------------------------------------------------
SETTLE = "usdt"
CONTRACT = "XRP_USDT"
NTFY_URL = "https://ntfy.sh/ALUR"

# Aturan Manajemen Risiko & Entri
MIN_SALDO_PERP = 0.50  # Batas bawah saldo untuk boleh trade ($0.50)
MARGIN_PER_TRADE = 0.10  # Margin entri per posisi ($0.10)
LEVERAGE = "50"  # Leverage 50x

# Aturan Jarak Tick
ENTRY_OFFSET_TICK = 10  # Mengantre 10 tick di bawah harga pasar
TRAILING_TICK = 100  # Jarak pelacakan profit (100 tick)
STOP_LOSS_TICK = 100  # Jarak potong rugi (100 tick)
# -----------------------------------------------------------------------------

def send_notification(message):
    """Fungsi helper untuk mengirim laporan teks langsung ke topic ntfy ALUR"""
    try:
        requests.post(
            NTFY_URL, 
            data=message.encode('utf-8'), 
            headers={"Title": "GATE.IO BOT PERPETUAL 50x"}
        )
        print("🤖 [ntfy] Laporan berhasil dikirim ke topic ALUR.")
    except Exception as e:
        print(f"❌ [ntfy] Gagal mengirim notifikasi: {e}")

def main():
    report = ["=== [LAPORAN BOT PERPETUAL XRP] ==="]
    
    # Ambil API KEY dari GitHub Secrets
    gate_key = os.environ.get("GATE_KEY")
    gate_secret = os.environ.get("GATE_SECRET")
    
    if not gate_key or not gate_secret:
        print("❌ Error: API Key atau Secret belum dikonfigurasi di GitHub Secrets!")
        return

    # Inisialisasi Klien API Gate.io
    config = gate_api.Configuration(key=gate_key, secret=gate_secret)
    client = gate_api.ApiClient(config)
    futures_api = gate_api.FuturesApi(client)

    try:
        # 1. CEK SALDO DOMPET PERPETUAL (USDT-M)
        # Diperbaiki ke list_futures_accounts agar sesuai dengan SDK Python Gate.io
        account = futures_api.list_futures_accounts(SETTLE)
        perp_usdt = float(account.available)
        report.append(f"• Saldo Perp Tersedia : ${perp_usdt:.4f}")

        # Filter Keamanan: Saldo harus di atas $0.50
        if perp_usdt < MIN_SALDO_PERP:
            report.append(f"⚠️ BATAL TRADE: Saldo tersedia (${perp_usdt:.4f}) di bawah batas minimum ${MIN_SALDO_PERP:.2f}!")
            send_notification("\n".join(report))
            return

        # 2. CEK MONOPOLI TRADE (Apakah ada order/posisi aktif)
        open_orders = futures_api.list_futures_orders(SETTLE, contract=CONTRACT, status="open")
        positions = futures_api.get_futures_position(SETTLE, CONTRACT)
        
        has_open_orders = len(open_orders) > 0
        has_active_position = float(positions.size) != 0

        if has_open_orders or has_active_position:
            report.append(f"🔒 SKIP TRADE: Ada {len(open_orders)} order mengantre atau posisi sedang berjalan.")
            send_notification("\n".join(report))
            return

        # 3. SET LEVERAGE KE 50x
        futures_api.update_position_leverage(SETTLE, CONTRACT, LEVERAGE)
        report.append(f"• Set Leverage        : {LEVERAGE}x")

        # 4. AMBIL DATA MARKET & HITUNG SPESIFIKASI ORDER
        tickers = futures_api.list_futures_tickers(SETTLE, contract=CONTRACT)
        last_price = float(tickers[0].last_price)
        
        contract_info = futures_api.get_futures_contract(SETTLE, CONTRACT)
        contract_size = float(contract_info.value_scale)  # Skala nilai 1 kontrak XRP
        tick_size = float(contract_info.order_price_round) or 0.0001  # Ukuran fraksi harga minimum

        # Perhitungan Harga (Entry, Trailing, SL)
        target_price = last_price - (ENTRY_OFFSET_TICK * tick_size)
        formatted_price = f"{target_price:.4f}"
        
        trailing_callback = f"{(TRAILING_TICK * tick_size):.4f}"
        sl_price = f"{(target_price - (STOP_LOSS_TICK * tick_size)):.4f}"

        # Perhitungan Jumlah Kontrak (Margin $0.10 * 50x Leverage = $5.00 Notional)
        target_notional = MARGIN_PER_TRADE * float(LEVERAGE)
        exact_size = target_notional / (target_price * contract_size)
        final_size = max(1, int(exact_size))  # Pembulatan ke bawah untuk keamanan ketat margin

        report.append(f"• Harga Pasar Saat Ini: ${last_price:.4f}")
        report.append(f"• Target Antrean Limit: ${formatted_price} (10 tick di bawah)")
        report.append(f"• Jarak Trailing Stop : {trailing_callback} USDT ({TRAILING_TICK} tick)")
        report.append(f"• Target Stop Loss    : ${sl_price} ({STOP_LOSS_TICK} tick di bawah entry)")
        report.append(f"• Kuantitas Pembelian : {final_size} kontrak (~${(final_size * contract_size * target_price / float(LEVERAGE)):.4f} real margin)")

        # 5. EKSEKUSI LIMIT ORDER BERANTAI (ENTRY + TRAILING + SL)
        order_payload = gate_api.FuturesOrder(
            contract=CONTRACT,
            size=final_size,  # Angka positif menandakan posisi LONG
            price=formatted_price,
            tif="gtc",        # Good 'Till Cancelled
            text="api_bot_50x",
            st_orders=[
                {
                    "rule": 1,               # Rule 1 = Trailing Stop / Profit Tracking
                    "trail_value": trailing_callback,
                    "order_type": "market"
                },
                {
                    "rule": 2,               # Rule 2 = Stop Loss
                    "trigger_price": sl_price,
                    "order_type": "market"
                }
            ]
        )

        # Kirim perintah order ke bursa Gate.io
        placed_order = futures_api.create_futures_order(SETTLE, order_payload)
        report.append(f"✅ BERHASIL PASANG ORDER LONG! ID: {placed_order.id}")
        
        # Kirim seluruh rangkuman sukses ke ntfy
        send_notification("\n".join(report))

    except Exception as e:
        print(f"Terjadi Kendala Sistem: {e}")
        report.append(f"❌ SYSTEM ERROR: {str(e)}")
        send_notification("\n".join(report))

if __name__ == "__main__":
    main()
