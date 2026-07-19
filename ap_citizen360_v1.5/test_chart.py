from my_agent.utils.chart_generator import generate_svg_chart
data = [
    {"district_name": "Srikakulam", "total_students": 500},
    {"district_name": "Visakhapatnam", "total_students": 1200}
]
svg = generate_svg_chart(data, "bar")
print(svg[:100] + "...")
