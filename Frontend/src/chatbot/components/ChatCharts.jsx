import React, { useRef } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend
} from 'recharts';

import html2canvas from 'html2canvas';

import {
  BarChart3,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  Download,
  FileDown
} from 'lucide-react';

const COLORS = [
  '#3B82F6',
  '#10B981',
  '#F59E0B',
  '#EF4444',
  '#8B5CF6',
  '#06B6D4',
  '#14B8A6',
  '#F97316'
];

export const ChatCharts = ({ chartData, summary }) => {
  const chartRef = useRef(null);

  if (!chartData) return null;

  const effectiveSummary = summary || chartData.summary;

  const getSafeFileName = (title = 'chart') =>
    title
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '_')
      .replace(/_+/g, '_');

  /**
   * Download Chart PNG
   */
  const handleDownloadPNG = async () => {
    try {
      if (!chartRef.current) return;

      const canvas = await html2canvas(chartRef.current, {
        scale: 2,
        backgroundColor: '#ffffff',
        useCORS: true
      });

      const image = canvas.toDataURL('image/png');

      const link = document.createElement('a');
      link.href = image;
      link.download = `${getSafeFileName(chartData.title)}.png`;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Failed downloading PNG', error);
    }
  };

  /**
   * Download Chart Data CSV
   */
  const handleDownloadCSV = () => {
    try {
      if (!chartData?.data?.length) return;

      const headers = Object.keys(chartData.data[0]);

      const csvRows = [
        headers.join(','),
        ...chartData.data.map((row) =>
          headers
            .map((header) =>
              `"${String(row[header] ?? '').replace(/"/g, '""')}"`
            )
            .join(',')
        )
      ];

      const csvContent = csvRows.join('\n');

      const blob = new Blob([csvContent], {
        type: 'text/csv;charset=utf-8;'
      });

      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = `${getSafeFileName(chartData.title)}.csv`;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed downloading CSV', error);
    }
  };

  const renderIcon = () => {
    switch (chartData.type) {
      case 'bar':
        return <BarChart3 size={15} />;
      case 'line':
        return <LineChartIcon size={15} />;
      case 'pie':
        return <PieChartIcon size={15} />;
      default:
        return <BarChart3 size={15} />;
    }
  };

  const CustomTooltip = ({
    active,
    payload,
    label
  }) => {
    if (!active || !payload?.length) return null;

    return (
      <div
        style={{
          background: '#ffffff',
          border: '1px solid #dbe2ef',
          borderRadius: '10px',
          padding: '10px 12px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)'
        }}
      >
        {label && (
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              color: '#111827'
            }}
          >
            {label}
          </div>
        )}

        {payload.map((item, index) => (
          <div
            key={index}
            style={{
              color: item.color,
              fontSize: 13
            }}
          >
            {item.name}: {item.value}
          </div>
        ))}
      </div>
    );
  };

  const renderBarChart = () => (
    <ResponsiveContainer width="100%" height={350}>
      <BarChart data={chartData.data}>
        <CartesianGrid strokeDasharray="3 3" />

        <XAxis
          dataKey={chartData.xKey}
          label={{
            value: chartData.xLabel,
            position: 'insideBottom',
            offset: -5
          }}
        />

        <YAxis
          label={{
            value: chartData.yLabel,
            angle: -90,
            position: 'insideLeft'
          }}
        />

        <Tooltip content={<CustomTooltip />} />

        <Bar
          dataKey={chartData.yKey}
          fill="#3B82F6"
          radius={[6, 6, 0, 0]}
          animationDuration={1500}
          animationEasing="ease-out"
        />
      </BarChart>
    </ResponsiveContainer>
  );

  const renderLineChart = () => (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={chartData.data}>
        <CartesianGrid strokeDasharray="3 3" />

        <XAxis
          dataKey={chartData.xKey}
          label={{
            value: chartData.xLabel,
            position: 'insideBottom',
            offset: -5
          }}
        />

        <YAxis
          label={{
            value: chartData.yLabel,
            angle: -90,
            position: 'insideLeft'
          }}
        />

        <Tooltip content={<CustomTooltip />} />

        <Line
          type="monotone"
          dataKey={chartData.yKey}
          stroke="#10B981"
          strokeWidth={3}
          dot={{ r: 5 }}
          activeDot={{ r: 8 }}
          animationDuration={1800}
          animationEasing="ease-in-out"
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderPieChart = () => (
    <ResponsiveContainer width="100%" height={350}>
      <PieChart>
        <Pie
          data={chartData.data}
          dataKey={chartData.valueKey}
          nameKey={chartData.nameKey}
          cx="50%"
          cy="50%"
          outerRadius={120}
          label
          animationDuration={1500}
        >
          {chartData.data.map((entry, index) => (
            <Cell
              key={index}
              fill={COLORS[index % COLORS.length]}
            />
          ))}
        </Pie>

        <Tooltip />

        <Legend
          formatter={(value) =>
            String(value)
              .replace(/_/g, ' ')
              .toUpperCase()
          }
        />

      </PieChart>
    </ResponsiveContainer>
  );

  const renderChart = () => {
    switch (chartData.type) {
      case 'bar':
        return renderBarChart();

      case 'line':
        return renderLineChart();

      case 'pie':
        return renderPieChart();

      default:
        return (
          <div
            style={{
              padding: '24px',
              textAlign: 'center'
            }}
          >
            Unsupported chart type: {chartData.type}
          </div>
        );
    }
  };

  return (
    <div className="cb-table-container">
        <div className="cb-table-card">
        <div className="cb-table-header">
            <div className="cb-table-title-row">
            {renderIcon()}

            <span className="cb-table-title">
                {chartData.title}
            </span>
            </div>

            <div className="cb-table-controls-row">
            <button
                type="button"
                className="cb-table-copy-btn"
                onClick={handleDownloadCSV}
            >
                <FileDown size={13} />
                <span>CSV</span>
            </button>

            <button
                type="button"
                className="cb-table-copy-btn"
                onClick={handleDownloadPNG}
            >
                <Download size={13} />
                <span>PNG</span>
            </button>

            <span className="cb-table-badge">
                {chartData.data?.length || 0} points
            </span>
            </div>
        </div>

        <div
            ref={chartRef}
            className="cb-chart-render-area"
            style={{
                width: '100%',
                minWidth: '700px',
                height: '420px',
                background: '#fff',
                padding: '16px'
            }}
            >
            {renderChart()}
        </div>
        </div>

        {effectiveSummary && (
        <div className="cb-summary-text">
            {effectiveSummary}
        </div>
        )}
    </div>
    );
};

export default ChatCharts;