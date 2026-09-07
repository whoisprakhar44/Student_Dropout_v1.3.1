import React, { useState, useMemo } from 'react';
import { User } from 'lucide-react';

import { ROLES } from '../constants/chatbotConstants';
import ChatTable from './ChatTable';
import ChatCharts from './ChatCharts';

import {
  BarChart3,
  LineChart,
  PieChart
} from 'lucide-react';

import {
  getSupportedCharts
} from '../utils/chartUtils';

export const ChatMessage = ({ message }) => {
  const isUser = message.role === ROLES.USER;

  const [activeChart, setActiveChart] = useState(null);

  const formatColumnLabel = (value = '') =>
    String(value)
      .replace(/_/g, ' ')
      .toUpperCase();

  const formattedTime = useMemo(() => {
    if (!message.timestamp) return '';

    try {
      const date = new Date(message.timestamp);

      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return '';
    }
  }, [message.timestamp]);

  const tablesList = useMemo(() => {
    if (Array.isArray(message.tables)) {
      return message.tables;
    }

    if (Array.isArray(message.tableData)) {
      return message.tableData;
    }

    if (
      message.tableData &&
      typeof message.tableData === 'object'
    ) {
      return [message.tableData];
    }

    return [];
  }, [message.tables, message.tableData]);

  const chartSupport = useMemo(() => {
    if (!tablesList.length) {
      return [];
    }

    try {
      return getSupportedCharts(tablesList[0]) || [];
    } catch (error) {
      console.error(
        'Failed determining chart support',
        error
      );
      return [];
    }
  }, [tablesList]);

  /**
   * Safely build chart configuration
   */
  const buildChartData = (tableData, chartType) => {
    if (!tableData) {
      return null;
    }

    const rows = Array.isArray(tableData.rows)
      ? tableData.rows
      : [];

    if (!rows.length) {
      return null;
    }

    let columns = [];

    // Preferred source
    if (Array.isArray(tableData.columns)) {
      columns = tableData.columns.map((column) =>
        typeof column === 'object'
          ? column.key || column.name
          : column
      );
    }

    // Fallback: infer from first row
    if (!columns.length) {
      columns = Object.keys(rows[0]);
    }

    if (columns.length < 2) {
      console.warn(
        'Unable to build chart. Need at least 2 columns.',
        columns
      );
      return null;
    }

    const [xKey, yKey] = columns;

    const xLabel = formatColumnLabel(xKey);
    const yLabel = formatColumnLabel(yKey);

    switch (chartType) {
      case 'bar':
        return {
          type: 'bar',
          title: tableData.title || 'Bar Chart',
          data: rows,
          xKey,
          yKey,
          xLabel,
          yLabel
        };

      case 'line':
        return {
          type: 'line',
          title: tableData.title || 'Line Chart',
          data: rows,
          xKey,
          yKey,
          xLabel,
          yLabel
        };

      case 'pie':
        return {
          type: 'pie',
          title: tableData.title || 'Pie Chart',
          data: rows,
          nameKey: xKey,
          valueKey: yKey,
          xLabel,
          yLabel
        };

      default:
        return null;
    }
  };

  const activeChartData =
    activeChart &&
    tablesList.length > 0
      ? buildChartData(
          tablesList[0],
          activeChart
        )
      : null;

  return (
    <div
      className={`cb-message-row ${
        isUser ? 'user' : 'assistant'
      }`}
    >
      <div className="cb-message-wrapper">
        {!isUser && (
          <div className="cb-message-avatar bot-avatar">
            <svg xmlns="http://www.w3.org/2000/svg" width="25.204" height="24.475" viewBox="0 0 25.204 24.475">
              <path id="chatbot-icon_1_" data-name="chatbot-icon (1)" d="M11.79,5.988V4.825a2.955,2.955,0,0,1-.41-.191,2.5,2.5,0,0,1-1.036-3.1,2.541,2.541,0,0,1,.541-.81,2.5,2.5,0,0,1,.8-.539A2.461,2.461,0,0,1,12.645,0,2.486,2.486,0,0,1,14.4,4.247l-.012.012a2.613,2.613,0,0,1-.484.375,2.309,2.309,0,0,1-.41.191V5.988h5.841A3.173,3.173,0,0,1,22.5,9.153v.47h1.083a1.626,1.626,0,0,1,1.62,1.622v3.767a1.626,1.626,0,0,1-1.62,1.622H22.508v.425a3.175,3.175,0,0,1-3.168,3.164H11.327l-4.8,4.124a.529.529,0,0,1-.749-.059.539.539,0,0,1-.129-.379L5.9,20.217H5.859A3.168,3.168,0,0,1,2.7,17.058v-.425H1.622A1.626,1.626,0,0,1,0,15.012V11.244A1.626,1.626,0,0,1,1.62,9.622H2.7V9.151a3.168,3.168,0,0,1,3.16-3.162ZM16.968,9.7a1.92,1.92,0,1,1-1.92,1.92,1.92,1.92,0,0,1,1.92-1.92Zm-8.732,0a1.92,1.92,0,1,1-1.92,1.92A1.92,1.92,0,0,1,8.236,9.7Zm1.308,6.431a.467.467,0,0,1-.078-.078.447.447,0,0,1-.107-.279.453.453,0,0,1,.094-.285.492.492,0,0,1,.08-.08.66.66,0,0,1,.8-.016,4.586,4.586,0,0,0,1.155.664,3.048,3.048,0,0,0,1.122.205,3.318,3.318,0,0,0,1.134-.226,5.207,5.207,0,0,0,1.179-.66.664.664,0,0,1,.8.037.615.615,0,0,1,.076.084.455.455,0,0,1,.086.287.478.478,0,0,1-.119.277.47.47,0,0,1-.088.078,6.273,6.273,0,0,1-1.5.82,4.569,4.569,0,0,1-1.544.293,4.352,4.352,0,0,1-1.55-.263,5.7,5.7,0,0,1-1.52-.853h0Zm9.793-9.081H5.859a2.1,2.1,0,0,0-2.1,2.1v7.906a2.1,2.1,0,0,0,2.1,2.1h.65A.535.535,0,0,1,7,19.725L6.8,22.715l3.958-3.406a.525.525,0,0,1,.375-.154h8.2a2.1,2.1,0,0,0,2.1-2.1V9.151a2.1,2.1,0,0,0-2.094-2.1Z" transform="translate(0 0)" fill="#0b2545"/>
            </svg>
          </div>
        )}

        <div className="cb-message-body">
          <div
            className="cb-message-bubble"
            aria-label={`${
              isUser
                ? 'You said'
                : 'Assistant responded'
            }: ${
              message.content || 'Data Result'
            }`}
          >
            {tablesList.map((table, index) => (
              <ChatTable
                key={index}
                tableData={table}
              />
            ))}

            {message.charts?.map(
              (chart, idx) => (
                <ChatCharts
                  key={idx}
                  chartData={chart}
                />
              )
            )}

            {message.content && (
              <div className="cb-message-content">
                {message.content}
              </div>
            )}

            {message.summary && (
              <div className="cb-summary-text">
                {message.summary}
              </div>
            )}
          </div>

          {!isUser &&
            tablesList.length > 0 &&
            chartSupport.length > 0 && (
              <div className="cb-chart-suggestions">
                {chartSupport.includes('bar') && (
                  <button
                    className={`cb-chart-btn ${
                      activeChart === 'bar'
                        ? 'active'
                        : ''
                    }`}
                    onClick={() =>
                      setActiveChart('bar')
                    }
                  >
                    <BarChart3 size={14} />
                    Bar Graph
                  </button>
                )}

                {chartSupport.includes('line') && (
                  <button
                    className={`cb-chart-btn ${
                      activeChart === 'line'
                        ? 'active'
                        : ''
                    }`}
                    onClick={() =>
                      setActiveChart('line')
                    }
                  >
                    <LineChart size={14} />
                    Line Chart
                  </button>
                )}

                {chartSupport.includes('pie') && (
                  <button
                    className={`cb-chart-btn ${
                      activeChart === 'pie'
                        ? 'active'
                        : ''
                    }`}
                    onClick={() =>
                      setActiveChart('pie')
                    }
                  >
                    <PieChart size={14} />
                    Pie Chart
                  </button>
                )}
              </div>
            )}

          {activeChartData && (
            <ChatCharts
              chartData={activeChartData}
            />
          )}

          {formattedTime && (
            <span className="cb-message-timestamp">
              {formattedTime}
            </span>
          )}
        </div>

        {isUser && (
          <div className="cb-message-avatar user-avatar">
            <User size={18} />
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;