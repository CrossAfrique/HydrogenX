# HydrogenX API

Professional green hydrogen project modeling platform backend built with FastAPI.

## Overview

HydrogenX is a comprehensive energy and hydrogen system modeling API that calculates:

- **System Sizing**: PV, battery, electrolyzer, fuel cell, H₂ storage
- **Financial Analysis**: CAPEX, OPEX, LCOE, LCOH, IRR, NPV, Payback Period
- **Revenue Streams**: Electricity, Heat, Oxygen
- **Monthly Analytics**: Revenue vs OPEX data for charting
- **Portfolio Support**: Aggregated metrics across multiple sites

## Features

✅ Single-site calculations with comprehensive metrics
✅ Portfolio-level analysis across multiple sites
✅ Configurable global parameters (discount rate, inflation, subsidies, pricing)
✅ User-defined battery and hydrogen autonomy hours
✅ Heat recovery from electrolyzer
✅ Oxygen revenue tracking
✅ Monthly data for revenue vs OPEX charting
✅ Professional Pydantic v2 models
✅ FastAPI with CORS and error handling
✅ OpenAPI/Swagger documentation

## Installation

### Prerequisites
- Python 3.10+
- pip or conda

### Setup

1. **Clone the repository**
   ```bash
   cd /workspaces/HydrogenX
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Server

### Development Mode
```bash
python main.py
```

The API will start on `http://localhost:8000`

### Alternative: Using uvicorn directly
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

### Interactive Documentation
Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Available Endpoints

#### Health Check
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-02T10:30:00.000000"
}
```

#### Single Site Calculation
```http
POST /api/v1/calculate_single_site
Content-Type: application/json
```

**Request Body:**
```json
{
  "site_name": "Site 1",
  "thermal_baseload": {
    "capacity_kwth": 100
  },
  "solar_pv": {
    "capacity_kwp": 500,
    "performance_ratio": 0.85
  },
  "battery_storage": {
    "capacity_kwh": 1000,
    "power_rating_kw": 200,
    "reserve_soc_percent": 20,
    "autonomy_hours": 4
  },
  "electrolyzer": {
    "power_kw": 200,
    "specific_energy_kwh_per_kg": 50,
    "heat_recovery_percent": 30
  },
  "hydrogen_storage": {
    "capacity_kg": 100,
    "autonomy_hours": 24
  },
  "fuel_cell": {
    "power_rating_kw": 200,
    "efficiency_percent": 60
  },
  "generator_grid": {
    "generator_capacity_kw": 300,
    "grid_import_limit_kw": 100
  },
  "global_params": {
    "discount_rate_percent": 8,
    "inflation_percent": 2.5,
    "subsidy_percent": 20,
    "electricity_price_usd_per_kwh": 0.12,
    "h2_price_usd_per_kg": 3.0,
    "heat_price_usd_per_kwh": 0.08,
    "oxygen_price_usd_per_kg": 0.1,
    "project_lifetime_years": 25,
    "operation_days_per_year": 330,
    "peak_sun_hours_per_day": 4.5
  }
}
```

**Response:**
```json
{
  "site_name": "Site 1",
  "timestamp": "2026-03-02T10:30:00.000000",
  "sizing": {
    "pv_capacity_kwp": 500,
    "battery_capacity_kwh": 2025,
    "electrolyzer_capacity_kw": 200,
    "h2_storage_capacity_kg": 150,
    "fuel_cell_capacity_kw": 200
  },
  "capex_breakdown": {
    "pv_capex_usd": 400000,
    "battery_capex_usd": 607500,
    "electrolyzer_capex_usd": 240000,
    "h2_storage_capex_usd": 7500,
    "fuel_cell_capex_usd": 300000,
    "bop_capex_usd": 288300,
    "total_capex_usd": 1843300,
    "after_subsidy_capex_usd": 1474640
  },
  "opex_breakdown": {
    "pv_battery_opex_usd_per_year": 8470,
    "electrolyzer_fc_opex_usd_per_year": 10800,
    "total_opex_usd_per_year": 20000
  },
  "revenue_streams": {
    "electricity_revenue_usd_per_year": 198000,
    "heat_revenue_usd_per_year": 4212,
    "oxygen_revenue_usd_per_year": 19800,
    "total_revenue_usd_per_year": 222012
  },
  "financial_metrics": {
    "lcoe_usd_per_kwh": 0.45,
    "lcoh_usd_per_kg": 12.5,
    "irr_percent": 15.2,
    "npv_usd": 850000,
    "payback_period_years": 7.2,
    "ebitda_usd_per_year": 202012
  },
  "monthly_data": [
    {
      "month": 1,
      "electricity_revenue": 16500,
      "heat_revenue": 351,
      "oxygen_revenue": 1650,
      "total_opex": 1667,
      "ebitda": 16834
    }
    // ... months 2-12
  ]
}
```

#### Portfolio Calculation
```http
POST /api/v1/calculate_portfolio
Content-Type: application/json
```

**Request Body:**
```json
{
  "portfolio_name": "Regional Portfolio",
  "sites": [
    {
      "site_name": "Site 1",
      "thermal_baseload": {...},
      "solar_pv": {...},
      // ... all other components
    },
    {
      "site_name": "Site 2",
      // ... site 2 parameters
    }
  ],
  "global_params": {
    "discount_rate_percent": 8,
    // ... all global parameters
  }
}
```

**Response:**
```json
{
  "portfolio_name": "Regional Portfolio",
  "timestamp": "2026-03-02T10:30:00.000000",
  "sites": [
    // ... individual site results
  ],
  "total_capex_usd": 3200000,
  "total_opex_usd_per_year": 40000,
  "total_revenue_usd_per_year": 440000,
  "total_ebitda_usd_per_year": 400000,
  "portfolio_irr_percent": 14.8,
  "portfolio_npv_usd": 1750000,
  "monthly_data": [
    // ... aggregated monthly data
  ]
}
```

## Project Structure

```
HydrogenX/
├── main.py                 # FastAPI application setup
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── models/
│   ├── __init__.py
│   └── schemas.py         # Pydantic v2 models (input/output)
├── routes/
│   ├── __init__.py
│   ├── health.py          # Health check endpoint
│   └── calculations.py    # Calculation endpoints
├── services/
│   ├── __init__.py
│   └── calculations.py    # Core calculation logic
└── utils/
    └── __init__.py
```

## Configuration

### Global Parameters

All global parameters are configurable per request:

| Parameter | Default | Range | Unit |
|-----------|---------|-------|------|
| discount_rate_percent | 8 | 0-30 | % |
| inflation_percent | 2.5 | 0-10 | % |
| subsidy_percent | 0 | 0-100 | % |
| electricity_price_usd_per_kwh | 0.12 | > 0 | USD/kWh |
| h2_price_usd_per_kg | 3.0 | > 0 | USD/kg |
| heat_price_usd_per_kwh | 0.08 | > 0 | USD/kWh |
| oxygen_price_usd_per_kg | 0.1 | > 0 | USD/kg |
| project_lifetime_years | 25 | 10-50 | years |
| operation_days_per_year | 330 | 200-365 | days |
| peak_sun_hours_per_day | 4.5 | 2.0-7.0 | hours |

## Calculation Methods

### Sizing
- **PV**: User-defined capacity
- **Battery**: Based on autonomy hours and daily energy
- **Electrolyzer**: User-defined power rating
- **H₂ Storage**: Based on autonomy hours and daily production
- **Fuel Cell**: User-defined power rating

### Financial Metrics
- **CAPEX**: Component costs + 15% Balance of Plant, minus subsidy
- **OPEX**: Annual maintenance costs as % of CAPEX by component
- **LCOE**: Levelized Cost of Electricity (assumes 80% to grid)
- **LCOH**: Levelized Cost of Hydrogen
- **IRR**: Internal Rate of Return (Newton-Raphson method)
- **NPV**: Net Present Value with inflation adjustments
- **Payback Period**: Simple payback in years

### Revenue Streams
- **Electricity**: Excess PV to grid at configured price
- **Heat**: From electrolyzer heat recovery (30% default)
- **Oxygen**: Byproduct of H₂ production (8 kg O₂ per kg H₂)
- **Hydrogen**: Direct H₂ sales

### Cost Data (Configurable)
```python
PV: $800/kWp, O&M 0.5%/year
Battery: $300/kWh, O&M 1%/year
Electrolyzer: $1,200/kW, O&M 2%/year
H₂ Storage: $50/kg, O&M 1.5%/year
Fuel Cell: $1,500/kW, O&M 2.5%/year
BOP: 15% of component costs, O&M 1%/year
```

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Successful calculation
- **422**: Validation error (invalid input)
- **500**: Internal server error
- **Detail**: Error messages in response body

## Integration with Frontend

The backend is designed to work with the HydrogenX frontend (React/Next.js):

1. All sidebar parameters map directly to `SingleSiteInput`
2. Revenue cards display values from `revenue_streams`
3. Monthly chart uses `monthly_data` for stacked bar visualization
4. Global parameters can be modified on the frontend

### Example Frontend Integration
```javascript
// POST to /api/v1/calculate_single_site
const response = await fetch('http://localhost:8000/api/v1/calculate_single_site', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(formData)
});

const result = await response.json();

// Update UI
setRevenueMetrics({
  electricity: result.revenue_streams.electricity_revenue_usd_per_year,
  heat: result.revenue_streams.heat_revenue_usd_per_year,
  oxygen: result.revenue_streams.oxygen_revenue_usd_per_year,
  total: result.revenue_streams.total_revenue_usd_per_year
});

setChartData(result.monthly_data);
```

## Testing

Run manual tests using Swagger UI or curl:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Single site calculation
curl -X POST http://localhost:8000/api/v1/calculate_single_site \
  -H "Content-Type: application/json" \
  -d @request.json
```

## Performance Considerations

- Single site calculation: ~50-100ms
- Portfolio with 10 sites: ~500-1000ms
- Monthly data generation: Included in main calculation
- No database required (stateless calculations)

## Future Enhancements

- [ ] Detailed hourly energy simulation
- [ ] Weather data integration for PV production
- [ ] Battery cycle life degradation
- [ ] Multi-year forecasting
- [ ] Sensitivity analysis
- [ ] Optimization algorithms for component sizing
- [ ] Database persistence for project history
- [ ] User authentication and project management
- [ ] Advanced scenario comparison
- [ ] Real-time energy market pricing

## Contributing

For issues or suggestions, please submit via GitHub issues.

## License

Proprietary - HydrogenX Platform

## Support

For technical support, contact the development team.

---

**Version**: 1.0.0
**Last Updated**: March 2, 2026
