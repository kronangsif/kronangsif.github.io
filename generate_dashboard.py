#!/usr/bin/env python3
"""Generate dashboard from collected data"""

import sqlite3
import os
import json
import math
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "collected.db")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

def get_stats():
    """Get statistics from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    stats = {}
    
    # Train statistics
    c.execute("""
        SELECT 
            COUNT(*) as total,
            MAX(collected_at) as latest,
            COUNT(DISTINCT location) as stations,
            AVG(time_deviation_minutes) as avg_delay,
            MAX(time_deviation_minutes) as max_delay,
            SUM(CASE WHEN time_deviation_minutes > 2 THEN 1 ELSE 0 END) as delayed_trains,
            COUNT(DISTINCT train_id) as unique_trains
        FROM train_announcements
    """)
    train = c.fetchone()
    stats['trains'] = {
        'total': train['total'] or 0,
        'latest': train['latest'] or '',
        'stations': train['stations'] or 0,
        'avg_delay': round(train['avg_delay'], 1) if train['avg_delay'] else 0,
        'max_delay': round(train['max_delay'], 1) if train['max_delay'] else 0,
        'delayed_trains': train['delayed_trains'] or 0,
        'unique_trains': train['unique_trains'] or 0,
        'on_time_pct': round(100 - (train['delayed_trains'] or 0) / train['total'] * 100, 1) if train['total'] > 0 else 100
    }
    
    # Train daily history (last 30 days)
    c.execute("""
        SELECT 
            DATE(collected_at) as date,
            COUNT(*) as total,
            SUM(CASE WHEN time_deviation_minutes > 2 THEN 1 ELSE 0 END) as delayed
        FROM train_announcements
        WHERE collected_at >= DATE('now', '-30 days')
        GROUP BY DATE(collected_at)
        ORDER BY date
    """)
    daily_history = []
    for row in c.fetchall():
        delayed_pct = round(row['delayed'] / row['total'] * 100, 1) if row['total'] > 0 else 0
        daily_history.append({
            'date': row['date'],
            'total': row['total'],
            'delayed': row['delayed'],
            'delayed_pct': delayed_pct
        })
    stats['trains']['daily_history'] = daily_history

    c.execute("""
        SELECT DATE(collected_at) as date,
               COUNT(*) as total,
               SUM(CASE WHEN time_deviation_minutes > 2 THEN 1 ELSE 0 END) as delayed
        FROM train_announcements
        WHERE collected_at >= DATE('now', '-6 days')
        GROUP BY DATE(collected_at)
        ORDER BY date
    """)
    train_recent = []
    for row in c.fetchall():
        delayed_pct = round(row['delayed'] / row['total'] * 100, 1) if row['total'] > 0 else 0
        train_recent.append({
            'date': row['date'],
            'total': row['total'],
            'delayed': row['delayed'],
            'delayed_pct': delayed_pct,
        })
    stats['trains']['recent_history'] = train_recent

    c.execute("""
        SELECT location, COUNT(*) as total, SUM(CASE WHEN time_deviation_minutes > 2 THEN 1 ELSE 0 END) as delayed, AVG(time_deviation_minutes) as avg_delay, MAX(time_deviation_minutes) as max_delay
        FROM train_announcements
        GROUP BY location
        ORDER BY delayed DESC, total DESC
        LIMIT 3
    """)
    station_top = []
    for row in c.fetchall():
        station_top.append({
            'location': row['location'],
            'total': row['total'] or 0,
            'delayed': row['delayed'] or 0,
            'avg_delay': round(row['avg_delay'], 1) if row['avg_delay'] else 0,
            'max_delay': round(row['max_delay'], 1) if row['max_delay'] else 0,
        })
    stats['trains']['top_stations'] = station_top

    c.execute("""
        SELECT train_id, location, advertised_time, estimated_time, time_deviation_minutes
        FROM train_announcements
        ORDER BY time_deviation_minutes DESC
        LIMIT 3
    """)
    train_big_delays = []
    for row in c.fetchall():
        train_big_delays.append({
            'train_id': row['train_id'],
            'location': row['location'],
            'advertised_time': row['advertised_time'],
            'estimated_time': row['estimated_time'],
            'time_deviation_minutes': round(row['time_deviation_minutes'], 1) if row['time_deviation_minutes'] else 0,
        })
    stats['trains']['big_delays'] = train_big_delays
    
    # Train delay histogram
    c.execute("""
        SELECT 
            CASE 
                WHEN time_deviation_minutes <= 0 THEN '0 (i tid)'
                WHEN time_deviation_minutes <= 10 THEN '1-10'
                WHEN time_deviation_minutes <= 20 THEN '11-20'
                WHEN time_deviation_minutes <= 30 THEN '21-30'
                WHEN time_deviation_minutes <= 60 THEN '31-60'
                ELSE '60+'
            END as range,
            COUNT(*) as count
        FROM train_announcements
        GROUP BY range
        ORDER BY CASE range
            WHEN '0 (i tid)' THEN 1
            WHEN '1-10' THEN 2
            WHEN '11-20' THEN 3
            WHEN '21-30' THEN 4
            WHEN '31-60' THEN 5
            WHEN '60+' THEN 6
        END
    """)
    histogram = []
    total = stats['trains']['total']
    for row in c.fetchall():
        histogram.append({
            'range': row['range'],
            'count': row['count'],
            'pct': round(row['count'] / total * 100, 1) if total > 0 else 0
        })
    stats['trains']['histogram'] = histogram
    
    # Weather statistics
    c.execute("""
        SELECT 
            COUNT(*) as total,
            MAX(timestamp) as latest,
            AVG(temperature) as avg_temp,
            MAX(temperature) as max_temp,
            MIN(temperature) as min_temp
        FROM weather
    """)
    weather = c.fetchone()
    stats['weather'] = {
        'total': weather['total'] or 0,
        'latest': weather['latest'] or '',
        'avg_temp': round(weather['avg_temp'], 1) if weather['avg_temp'] else 0,
        'max_temp': round(weather['max_temp'], 1) if weather['max_temp'] else 0,
        'min_temp': round(weather['min_temp'], 1) if weather['min_temp'] else 0
    }
    
    # Weather history (last 30 days)
    c.execute("""
        SELECT 
            DATE(timestamp) as date,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            AVG(temperature) as avg_temp
        FROM weather
        WHERE timestamp >= DATE('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    """)
    weather_history = []
    for row in c.fetchall():
        weather_history.append({
            'date': row['date'][5:],  # Skip year
            'min': round(row['min_temp'], 1) if row['min_temp'] else 0,
            'max': round(row['max_temp'], 1) if row['max_temp'] else 0,
            'avg': round(row['avg_temp'], 1) if row['avg_temp'] else 0
        })
    stats['weather']['history'] = weather_history
    
    # Electricity statistics
    c.execute("""
        SELECT 
            COUNT(*) as total,
            MAX(time_start) as latest,
            AVG(sek_per_kwh) as avg_price,
            MIN(sek_per_kwh) as min_price,
            MAX(sek_per_kwh) as max_price
        FROM electricity_prices
    """)
    elec = c.fetchone()
    stats['electricity'] = {
        'total': elec['total'] or 0,
        'latest': elec['latest'] or '',
        'avg_price': round(elec['avg_price'], 2) if elec['avg_price'] else 0,
        'min_price': round(elec['min_price'], 2) if elec['min_price'] else 0,
        'max_price': round(elec['max_price'], 2) if elec['max_price'] else 0
    }
    
    # Electricity history
    c.execute("""
        SELECT 
            DATE(time_start) as date,
            MIN(sek_per_kwh) as min_price,
            MAX(sek_per_kwh) as max_price,
            AVG(sek_per_kwh) as avg_price
        FROM electricity_prices
        WHERE time_start >= DATE('now', '-30 days')
        GROUP BY DATE(time_start)
        ORDER BY date
    """)
    elec_history = []
    for row in c.fetchall():
        elec_history.append({
            'date': row['date'][5:],
            'min': round(row['min_price'], 2) if row['min_price'] else 0,
            'max': round(row['max_price'], 2) if row['max_price'] else 0,
            'avg': round(row['avg_price'], 2) if row['avg_price'] else 0
        })
    stats['electricity']['history'] = elec_history

    c.execute("SELECT MAX(substr(time_start, 1, 10)) as latest_day FROM electricity_prices")
    elec_day = c.fetchone()
    latest_day = elec_day['latest_day'] or ''

    c.execute("""
        SELECT COUNT(*) as total_readings
        FROM electricity_prices
        WHERE substr(time_start, 1, 10) = ?
    """, (latest_day,))
    elec_day_stats = c.fetchone()

    c.execute("""
        SELECT time_start, sek_per_kwh
        FROM electricity_prices
        WHERE substr(time_start, 1, 10) = ?
        ORDER BY sek_per_kwh DESC, time_start ASC
        LIMIT 3
    """, (latest_day,))
    elec_peak_hours = []
    for row in c.fetchall():
        elec_peak_hours.append({
            'time': row['time_start'][11:16],
            'price': round(row['sek_per_kwh'], 2) if row['sek_per_kwh'] else 0,
        })

    c.execute("""
        SELECT time_start, sek_per_kwh
        FROM electricity_prices
        WHERE substr(time_start, 1, 10) = ?
        ORDER BY sek_per_kwh ASC, time_start ASC
        LIMIT 3
    """, (latest_day,))
    elec_low_hours = []
    for row in c.fetchall():
        elec_low_hours.append({
            'time': row['time_start'][11:16],
            'price': round(row['sek_per_kwh'], 2) if row['sek_per_kwh'] else 0,
        })

    stats['electricity']['latest_day'] = latest_day
    stats['electricity']['latest_day_readings'] = elec_day_stats['total_readings'] or 0
    stats['electricity']['peak_hours'] = elec_peak_hours
    stats['electricity']['low_hours'] = elec_low_hours
    
    # Property statistics
    c.execute("SELECT MAX(year) as latest_year FROM property_transfers")
    prop_latest = c.fetchone()
    latest_year = prop_latest['latest_year'] or ''

    c.execute("""
        SELECT
            COALESCE(SUM(count), 0) as total_sales,
            COALESCE(SUM(total_value_tkr), 0) as total_value_tkr
        FROM property_transfers
        WHERE year = ?
    """, (latest_year,))
    prop_totals = c.fetchone()
    total_sales = prop_totals['total_sales'] or 0
    total_value_tkr = prop_totals['total_value_tkr'] or 0
    avg_value_tkr = round(total_value_tkr / total_sales, 1) if total_sales else 0

    c.execute("""
        SELECT region_name, count, total_value_tkr
        FROM property_transfers
        WHERE year = ?
        ORDER BY count DESC
        LIMIT 5
    """, (latest_year,))
    prop_top_regions = []
    for row in c.fetchall():
        region_count = row['count'] or 0
        region_total_value_tkr = row['total_value_tkr'] or 0
        prop_top_regions.append({
            'region_name': row['region_name'],
            'count': region_count,
            'total_value_tkr': region_total_value_tkr,
            'avg_value_tkr': round(region_total_value_tkr / region_count, 1) if region_count else 0,
        })

    stats['property'] = {
        'total_sales': total_sales,
        'total_value_tkr': total_value_tkr,
        'avg_value_tkr': avg_value_tkr,
        'latest_year': latest_year,
        'top_regions': prop_top_regions,
    }
    
    conn.close()
    return stats

def get_dashboard_timestamp(stats):
    """Use the freshest collected data timestamp instead of wall-clock render time."""
    candidates = []
    for key in ('trains', 'weather', 'electricity'):
        value = stats.get(key, {}).get('latest', '')
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            candidates.append(parsed)
        except ValueError:
            continue
    if not candidates:
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    return max(candidates).strftime('%Y-%m-%d %H:%M')

def generate_html(stats):
    """Generate dashboard HTML"""
    
    # Generate weather chart points from stats
    history = stats.get('weather', {}).get('history', [])
    max_temps = [h.get('max', 0) for h in history]
    min_temps = [h.get('min', 0) for h in history]
    all_temps = max_temps + min_temps
    weather_chart_html = '<div class="trend-empty">Inga väderdata ännu</div>'
    if history and all_temps:
        chart_min = math.floor(min(all_temps) - 2)
        chart_max = math.ceil(max(all_temps) + 2)
        if chart_min == chart_max:
            chart_min -= 1
            chart_max += 1

        left_margin = 44
        right_margin = 10
        top_margin = 12
        bottom_margin = 28
        plot_height = 150
        plot_width = max(1, (len(history) - 1) * 60)
        view_width = left_margin + plot_width + right_margin
        view_height = top_margin + plot_height + bottom_margin

        def x_for(index):
            if len(history) == 1:
                return left_margin + plot_width / 2
            return left_margin + (plot_width * index / (len(history) - 1))

        def y_for(value):
            return top_margin + ((chart_max - value) / (chart_max - chart_min) * plot_height)

        max_points = ','.join([
            f"{x_for(i):.1f},{y_for(h.get('max', 0)):.1f}"
            for i, h in enumerate(history)
        ])
        min_points = ','.join([
            f"{x_for(i):.1f},{y_for(h.get('min', 0)):.1f}"
            for i, h in enumerate(history)
        ])
        band_points = ' '.join([
            f"{x_for(i):.1f},{y_for(h.get('max', 0)):.1f}"
            for i, h in enumerate(history)
        ] + [
            f"{x_for(i):.1f},{y_for(h.get('min', 0)):.1f}"
            for i, h in reversed(list(enumerate(history)))
        ])
        y_ticks = [chart_max - ((chart_max - chart_min) * i / 4) for i in range(5)]
        grid_lines = ''.join([
            f'<line class="weather-grid-line" x1="{left_margin}" y1="{y_for(tick):.1f}" x2="{left_margin + plot_width}" y2="{y_for(tick):.1f}" />'
            for tick in y_ticks
        ])
        y_labels = ''.join([
            f'<text class="weather-axis-label" x="34" y="{y_for(tick) + 4:.1f}" text-anchor="end">{tick:g}°</text>'
            for tick in y_ticks
        ])
        date_label_items = []
        for i, item in enumerate(history):
            if i not in {0, len(history) - 1} and i % 5 != 0:
                continue
            date_label_items.append(f'<span title="{item.get("date", "")}">{item.get("date", "")}</span>')
        date_labels = ''.join(date_label_items)
        weather_chart_html = f"""
                <div class="weather-chart">
                    <div class="weather-legend" aria-hidden="true">
                        <span><i class="legend-swatch legend-max"></i> Max</span>
                        <span><i class="legend-swatch legend-min"></i> Min</span>
                    </div>
                    <svg viewBox="0 0 {view_width} {view_height}" preserveAspectRatio="none" role="img" aria-label="Temperaturgraf med y-axel och temperaturband">
                        <g class="weather-grid">{grid_lines}</g>
                        <g class="weather-axis">{y_labels}</g>
                        <polygon class="weather-band" points="{band_points}"/>
                        <polyline class="weather-line-max" points="{max_points}"/>
                        <polyline class="weather-line-min" points="{min_points}"/>
                        {''.join([f'<circle class="weather-dot weather-dot-max" cx="{x_for(i):.1f}" cy="{y_for(h.get("max", 0)):.1f}" r="3.2"><title>{h.get("date", "")} max {h.get("max", 0):g}°</title></circle>' for i, h in enumerate(history)])}
                        {''.join([f'<circle class="weather-dot weather-dot-min" cx="{x_for(i):.1f}" cy="{y_for(h.get("min", 0)):.1f}" r="3.2"><title>{h.get("date", "")} min {h.get("min", 0):g}°</title></circle>' for i, h in enumerate(history)])}
                    </svg>
                </div>
                <div class="date-labels">{date_labels}</div>
        """
    
    last_updated = get_dashboard_timestamp(stats)
    property_top_regions = ''.join([
        f'<li><div class="mini-list-main"><span>{r["region_name"]}</span><small>{r["count"]:,} försäljningar</small></div><strong>{r["avg_value_tkr"] / 1000:.1f} Mkr</strong></li>'
        for r in stats['property']['top_regions']
    ]) or '<li><span>Inga datapunkter ännu</span><strong>0</strong></li>'
    train_recent_history = stats['trains'].get('recent_history', [])
    train_recent_max_pct = max((day.get('delayed_pct', 0) for day in train_recent_history), default=0)
    train_recent_cards = ''
    for day in train_recent_history:
        if train_recent_max_pct > 0:
            fill_pct = max(12, int(round((day['delayed_pct'] / train_recent_max_pct) * 100)))
        else:
            fill_pct = 12
        train_recent_cards += (
            '<div class="recent-week-card">'
            f'<div class="recent-week-head"><span>{day["date"][5:]}</span><strong>{day["delayed_pct"]:.1f}%</strong></div>'
            f'<div class="recent-week-track" aria-hidden="true"><div class="recent-week-fill" style="width: {fill_pct}%;"></div></div>'
            f'<div class="recent-week-foot">{day["delayed"]:,} försenade av {day["total"]:,}</div>'
            '</div>'
        )
    train_recent_cards = train_recent_cards or '<div class="trend-empty">Inga dagdata ännu</div>'
    train_station_list = ''.join([
        f'<li><span>{row["location"]}</span><strong>{row["delayed"]:,} förs.</strong></li>'
        for row in stats['trains'].get('top_stations', [])
    ]) or '<li><span>Inga stationer ännu</span><strong>0</strong></li>'
    train_big_delay_list = ''.join([
        f'<li><span>{row["location"]} {row["time_deviation_minutes"]:.0f}m</span><strong>{row["advertised_time"][11:16] if row["advertised_time"] else ""}</strong></li>'
        for row in stats['trains'].get('big_delays', [])
    ]) or '<li><span>Inga förseningar ännu</span><strong>0</strong></li>'
    electricity_history = stats['electricity'].get('history', [])
    electricity_bars = ''.join([
        f'<div class="trend-bar" style="height: {max(6, min(100, int(round(day["avg"] * 60))))}%;"><span>{day["date"]}</span><strong>{day["avg"]:.2f}</strong></div>'
        for day in electricity_history[-7:]
    ]) or '<div class="trend-empty">Inga historikdagar ännu</div>'
    electricity_peaks = ''.join([
        f'<li><span>{row["time"]}</span><strong>{row["price"]:.2f} kr</strong></li>'
        for row in stats['electricity']['peak_hours']
    ]) or '<li><span>Inga toppar ännu</span><strong>0 kr</strong></li>'
    electricity_lows = ''.join([
        f'<li><span>{row["time"]}</span><strong>{row["price"]:.2f} kr</strong></li>'
        for row in stats['electricity']['low_hours']
    ]) or '<li><span>Inga bottnar ännu</span><strong>0 kr</strong></li>'

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Dashboard - FluxWeaver</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; margin-bottom: 10px; }}
        .last-update {{ color: #64748b; margin-bottom: 30px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
        .card.trains {{ border-top: 4px solid #f97316; }}
        .card.weather {{ border-top: 4px solid #06b6d4; }}
        .card.electricity {{ border-top: 4px solid #eab308; }}
        .card.property {{ border-top: 4px solid #8b5cf6; }}
        .card.heatmap {{ border-top: 4px solid #22c55e; }}
        .card h2 {{ margin-bottom: 20px; font-size: 1.2rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }}
        .stat {{ background: #334155; padding: 15px; border-radius: 8px; }}
        .stat-label {{ color: #94a3b8; font-size: 0.85rem; }}
        .stat-value {{ font-size: 1.5rem; font-weight: bold; margin-top: 5px; }}
        .stat-value.delay {{ color: #f97316; }}
        .stat-value.on-time {{ color: #22c55e; }}
        .card-link {{ display: inline-flex; align-items: center; justify-content: center; margin-top: 18px; padding: 12px 16px; border-radius: 999px; background: linear-gradient(135deg, #22c55e, #06b6d4); color: #0f172a; font-weight: 800; text-decoration: none; }}
        .card-link:hover {{ opacity: 0.92; }}
        .card-copy {{ color: #94a3b8; line-height: 1.55; margin-bottom: 18px; }}
        .mini-list {{ list-style: none; margin-top: 16px; display: grid; gap: 8px; }}
        .mini-list li {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 10px 12px; border-radius: 10px; background: rgba(51, 65, 85, 0.7); color: #cbd5e1; }}
        .mini-list li span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .mini-list-main {{ display: grid; gap: 2px; min-width: 0; }}
        .mini-list-main small {{ color: #94a3b8; font-size: 0.76rem; }}
        .mini-list li strong {{ color: #f8fafc; font-size: 1rem; }}
        .property-note {{ color: #94a3b8; font-size: 0.9rem; margin-top: 10px; line-height: 1.5; }}
        .trend {{ margin-top: 16px; }}
        .trend-chart {{ height: 140px; display: grid; grid-template-columns: repeat(auto-fit, minmax(42px, 1fr)); align-items: end; gap: 8px; }}
        .trend-bar {{ position: relative; min-height: 18px; border-radius: 10px 10px 4px 4px; background: linear-gradient(180deg, rgba(234, 179, 8, 0.95), rgba(249, 115, 22, 0.95)); display: flex; flex-direction: column; justify-content: flex-end; padding: 10px 8px 8px; overflow: hidden; }}
        .trend-bar span {{ display: block; font-size: 0.68rem; color: rgba(15, 23, 42, 0.9); font-weight: 800; }}
        .trend-bar strong {{ display: block; margin-top: 4px; font-size: 0.85rem; color: rgba(15, 23, 42, 0.95); }}
        .trend-empty {{ color: #94a3b8; padding: 12px 0; }}
        .train-bar {{ background: linear-gradient(180deg, rgba(249, 115, 22, 0.95), rgba(234, 88, 12, 0.95)); }}
        .recent-week-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 10px; margin-top: 14px; }}
        .recent-week-card {{ background: rgba(51, 65, 85, 0.7); border-radius: 12px; padding: 12px; display: grid; gap: 10px; }}
        .recent-week-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }}
        .recent-week-head span {{ color: #cbd5e1; font-weight: 700; font-size: 0.9rem; }}
        .recent-week-head strong {{ color: #f8fafc; font-size: 1.05rem; }}
        .recent-week-track {{ height: 10px; border-radius: 999px; background: rgba(15, 23, 42, 0.55); overflow: hidden; }}
        .recent-week-fill {{ height: 100%; border-radius: inherit; background: linear-gradient(90deg, #fb923c, #ea580c); }}
        .recent-week-foot {{ color: #94a3b8; font-size: 0.82rem; }}
        .split-panels {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 14px; }}
        .split-panel h3 {{ margin: 0 0 10px; font-size: 0.92rem; color: #f8fafc; }}
        .split-panel ul {{ list-style: none; display: grid; gap: 8px; }}
        .split-panel li {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 8px 10px; border-radius: 10px; background: rgba(51, 65, 85, 0.7); color: #cbd5e1; }}
        
        .history-section {{ margin-top: 30px; }}
        .history-section h3 {{ color: #00d4ff; margin-bottom: 15px; }}
        .history-chart {{ display: flex; align-items: flex-end; gap: 4px; height: 150px; padding: 10px 0; }}
        .history-bar {{ flex: 1; background: #22c55e; min-height: 2px; border-radius: 2px 2px 0 0; position: relative; }}
        .history-bar:hover {{ opacity: 0.8; }}
        .history-bar .tooltip {{ display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #000; padding: 5px 10px; border-radius: 4px; font-size: 0.8rem; white-space: nowrap; }}
        .history-bar:hover .tooltip {{ display: block; }}
        
        .histogram {{ display: flex; gap: 10px; margin-top: 20px; }}
        .hist-bar {{ flex: 1; text-align: center; }}
        .hist-bar-value {{ height: 100px; background: #334155; border-radius: 4px; display: flex; flex-direction: column; justify-content: flex-end; }}
        .hist-bar-fill {{ width: 100%; background: #f97316; border-radius: 4px 4px 0 0; }}
        .hist-label {{ font-size: 0.75rem; color: #94a3b8; margin-top: 5px; }}
        
        .weather-chart {{ height: 200px; position: relative; margin-top: 20px; }}
        .weather-legend {{ display: flex; gap: 14px; align-items: center; justify-content: flex-end; margin-bottom: 10px; color: #cbd5e1; font-size: 0.8rem; font-weight: 700; }}
        .weather-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
        .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; display: inline-block; }}
        .legend-max {{ background: #ef4444; }}
        .legend-min {{ background: #3b82f6; }}
        .weather-chart svg {{ width: 100%; height: 100%; }}
        .weather-grid-line {{ stroke: rgba(148, 163, 184, 0.18); stroke-width: 1; stroke-dasharray: 4 6; }}
        .weather-axis-label {{ fill: #94a3b8; font-size: 12px; font-weight: 700; }}
        .weather-band {{ fill: rgba(56, 189, 248, 0.10); stroke: none; }}
        .weather-line-max {{ stroke: #ef4444; stroke-width: 3; fill: none; filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.3)); }}
        .weather-line-min {{ stroke: #3b82f6; stroke-width: 3; fill: none; filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.3)); }}
        .weather-dot-max {{ fill: #ef4444; }}
        .weather-dot-min {{ fill: #3b82f6; }}
        .weather-dot {{ stroke: #0f172a; stroke-width: 1.5; }}
        .date-labels {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(44px, 1fr)); gap: 8px; margin-top: 10px; }}
        .date-labels span {{ font-size: 0.75rem; color: #64748b; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        @media (max-width: 640px) {{
            .recent-week-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Data Dashboard</h1>
        <p class="last-update">Uppdaterad: {last_updated}</p>
        
        <div class="grid">
            <div class="card trains">
                <h2>🚅 Tåg</h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Totalt</div>
                        <div class="stat-value">{stats['trains']['total']:,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Unika tåg</div>
                        <div class="stat-value">{stats['trains']['unique_trains']:,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Stationer</div>
                        <div class="stat-value">{stats['trains']['stations']}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Försenade</div>
                        <div class="stat-value delay">{stats['trains']['delayed_trains']:,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">I tid</div>
                        <div class="stat-value on-time">{stats['trains']['on_time_pct']}%</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Snittförsening</div>
                        <div class="stat-value delay">{stats['trains']['avg_delay']} min</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Max försening</div>
                        <div class="stat-value delay-large">{stats['trains']['max_delay']} min</div>
                    </div>
                </div>
                
                <div class="history-section">
                    <h3>📈 30 dagars historik</h3>
                    <div class="history-chart">
                        {''.join([f'<div class="history-bar" style="height: {d["delayed_pct"]}%; background: {"#22c55e" if d["delayed_pct"] < 20 else "#eab308" if d["delayed_pct"] < 40 else "#ef4444"};"><span class="tooltip">{d["date"]}<br>{d["delayed_pct"]}% försenade</span></div>' for d in stats['trains']['daily_history']])}
                    </div>
                </div>

                <div class="trend">
                    <h3>📉 Senaste 7 dagarna</h3>
                    <div class="recent-week-grid">
                        {train_recent_cards}
                    </div>
                </div>

                <div class="history-section">
                    <h3>Fördelning av förseningar</h3>
                    <div class="histogram">
                        {''.join([f'<div class="hist-bar"><div class="hist-bar-value"><div class="hist-bar-fill" style="height: {h["pct"]}%;"></div></div><div class="hist-label">{h["range"]}<br>{h["count"]:,}</div></div>' for h in stats['trains']['histogram']])}
                    </div>
                </div>

                <div class="split-panels">
                    <div class="split-panel">
                        <h3>Störst försening per station</h3>
                        <ul>
                            {train_station_list}
                        </ul>
                    </div>
                    <div class="split-panel">
                        <h3>Värsta enskilda förseningar</h3>
                        <ul>
                            {train_big_delay_list}
                        </ul>
                    </div>
                </div>
            </div>
            
            <div class="card weather">
                <h2>🌤️ Väder</h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Totalt</div>
                        <div class="stat-value">{stats['weather']['total']:,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Medeltemp</div>
                        <div class="stat-value">{stats['weather']['avg_temp']}°</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Högst</div>
                        <div class="stat-value" style="color: #ef4444;">{stats['weather']['max_temp']}°</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Lägst</div>
                        <div class="stat-value" style="color: #3b82f6;">{stats['weather']['min_temp']}°</div>
                    </div>
                </div>
                
                <div class="history-section">
                    <h3>📈 Temperatur (senaste 30 dagarna)</h3>
                    {weather_chart_html}
                </div>
            </div>
            
            <div class="card electricity">
                <h2>⚡ Elpriser</h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Senaste dag</div>
                        <div class="stat-value">{stats['electricity'].get('latest_day') or '—'}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Mätpunkter</div>
                        <div class="stat-value">{stats['electricity'].get('latest_day_readings', 0):,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Snitt</div>
                        <div class="stat-value">{stats['electricity']['avg_price']} kr</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Spread</div>
                        <div class="stat-value">{(stats['electricity']['max_price'] - stats['electricity']['min_price']) if stats['electricity']['total'] else 0:.2f} kr</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Lägst</div>
                        <div class="stat-value" style="color: #22c55e;">{stats['electricity']['min_price']} kr</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Högst</div>
                        <div class="stat-value" style="color: #ef4444;">{stats['electricity']['max_price']} kr</div>
                    </div>
                </div>

                <div class="trend">
                    <h3>📈 Dagstrend</h3>
                    <div class="trend-chart">
                        {electricity_bars}
                    </div>
                </div>

                <div class="split-panels">
                    <div class="split-panel">
                        <h3>Dyraste timmarna</h3>
                        <ul>
                            {electricity_peaks}
                        </ul>
                    </div>
                    <div class="split-panel">
                        <h3>Billigaste timmarna</h3>
                        <ul>
                            {electricity_lows}
                        </ul>
                    </div>
                </div>
            </div>
            
            <div class="card property">
                <h2>🏠 Fastigheter</h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Senaste år</div>
                        <div class="stat-value">{stats['property']['latest_year'] or '—'}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Sålda objekt</div>
                        <div class="stat-value">{stats['property']['total_sales']:,}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Genomsnittligt värde</div>
                        <div class="stat-value">{stats['property']['avg_value_tkr'] / 1000:.1f} Mkr</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Topplän</div>
                        <div class="stat-value">{stats['property']['top_regions'][0]['region_name'] if stats['property']['top_regions'] else '—'}</div>
                    </div>
                </div>
                <ul class="mini-list">
                    {property_top_regions}
                </ul>
                <p class="property-note">Visar småhus för senaste året. Värdet är nu snitt per försäljning och regionraderna visar genomsnittspriset i stället för totalsumman, vilket gör kortet lättare att jämföra mellan regioner.</p>
            </div>

            <div class="card heatmap">
                <h2>🗺️ Förseningar över Sverige</h2>
                <p class="card-copy">Ny sida med Sverigekarta och station-heatmap per timme och veckodag. Beräknas direkt från SQLite och uppdateras tillsammans med datan.</p>
                <a class="card-link" href="delay-heatmap.html">Öppna heatmapen</a>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html

def main():
    print("Generating dashboard...")
    stats = get_stats()
    print(
        "Stats summary: "
        f"trains={stats['trains']['total']}, "
        f"weather={stats['weather']['total']}, "
        f"electricity={stats['electricity']['total']}, "
        f"property={stats['property']['total_sales']}"
    )
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    html = generate_html(stats)
    with open(OUTPUT_PATH, 'w') as f:
        f.write(html)
    
    print(f"Dashboard written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
