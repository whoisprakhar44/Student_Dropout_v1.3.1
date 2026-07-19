import json
import logging
from typing import Any
import vl_convert as vlc
from langchain_core.messages import SystemMessage, HumanMessage

from my_agent.utils.nodes import _intent_model

logger = logging.getLogger("chart-generator")

def generate_svg_chart(data: list[dict[str, Any]], chart_type: str) -> str:
    if not data:
        raise ValueError("Cannot generate chart from empty data.")

    first_row = data[0]
    schema_hint = {k: type(v).__name__ for k, v in first_row.items()}

    prompt = f"""
You are an expert data visualization assistant.
Given the following data schema (columns and their types) and a requested chart type,
select the best column for the X-axis (usually nominal/categorical like string or date)
and the best column for the Y-axis (usually quantitative/numeric like int or float).

If the chart is a 'pie' chart, X acts as the color/category label, and Y acts as the arc value (theta).

Schema: {json.dumps(schema_hint)}
Requested Chart Type: {chart_type}

Return EXACTLY and ONLY a JSON object with this format:
{{"x": "column_name", "y": "column_name"}}
Do NOT include markdown backticks or any other text.
"""
    try:
        response = _intent_model.invoke([HumanMessage(content=prompt)])
        raw_text = response.content.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        
        mapping = json.loads(raw_text.strip())
        x_field = mapping.get("x")
        y_field = mapping.get("y")
        
        if not x_field or not y_field or x_field not in first_row or y_field not in first_row:
            x_field = next((k for k, v in schema_hint.items() if v == "str"), list(schema_hint.keys())[0])
            y_field = next((k for k, v in schema_hint.items() if v in ("int", "float")), list(schema_hint.keys())[-1])
            
    except Exception as e:
        logger.warning(f"Failed to infer axes via LLM, falling back to heuristics: {e}")
        x_field = next((k for k, v in schema_hint.items() if v == "str"), list(schema_hint.keys())[0])
        y_field = next((k for k, v in schema_hint.items() if v in ("int", "float")), list(schema_hint.keys())[-1])

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": f"{chart_type.title()} chart of {y_field} by {x_field}",
        "data": {"values": data},
        "background": "transparent",
        "config": {
            "axis": {
                "labelColor": "#94a3b8",
                "titleColor": "#94a3b8",
                "gridColor": "#1e293b",
                "domainColor": "#334155"
            },
            "legend": {
                "labelColor": "#94a3b8",
                "titleColor": "#94a3b8"
            },
            "title": {
                "color": "#f8fafc"
            }
        }
    }

    if chart_type.lower() == "pie":
        spec["mark"] = {"type": "arc", "innerRadius": 0}
        spec["encoding"] = {
            "theta": {"field": y_field, "type": "quantitative"},
            "color": {"field": x_field, "type": "nominal"}
        }
    elif chart_type.lower() == "scatter":
        spec["mark"] = "point"
        spec["encoding"] = {
            "x": {"field": x_field, "type": "quantitative"},
            "y": {"field": y_field, "type": "quantitative"}
        }
    else:
        spec["mark"] = {"type": chart_type.lower(), "tooltip": True}
        spec["encoding"] = {
            "x": {"field": x_field, "type": "nominal", "axis": {"labelAngle": -45}},
            "y": {"field": y_field, "type": "quantitative"}
        }
        if chart_type.lower() == "bar":
            spec["encoding"]["color"] = {"value": "#6366f1"}
        elif chart_type.lower() == "line":
            spec["encoding"]["color"] = {"value": "#a855f7"}

    svg_str = vlc.vegalite_to_svg(spec)
    return svg_str
