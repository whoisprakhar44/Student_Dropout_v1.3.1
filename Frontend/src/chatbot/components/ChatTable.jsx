import React, { useState, useMemo } from 'react';
import { Table, Search, Copy, Check, Download, FileSpreadsheet } from 'lucide-react';

/**
 * Robust Chat Table Component for displaying SQL Query Results & Structured Data
 * 
 * Supports:
 * - Tuple rows (Array of Arrays) & Object rows (Array of Objects)
 * - Dynamic columns detection
 * - Client-side search filtering
 * - Copy to CSV format
 * - Download CSV & Download Excel (.xls) file exports
 * - Inline plain text summary rendering (no callout box card)
 * - Empty row handling (hides table, shows summary text)
 */
export const ChatTable = ({ tableData, summary }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [copied, setCopied] = useState(false);

  // Normalize tableData structure
  const normalized = useMemo(() => {
    if (!tableData) return null;

    let cols = [];
    let rows = [];
    let title = tableData.title || 'SQL Query Result';

    if (Array.isArray(tableData.columns)) {
      cols = tableData.columns.map(c => (typeof c === 'object' ? c.label || c.key : String(c)));
    }

    if (Array.isArray(tableData.rows)) {
      rows = tableData.rows;

      // Auto-extract columns from Array of Objects if columns omitted
      if (cols.length === 0 && rows.length > 0 && typeof rows[0] === 'object' && !Array.isArray(rows[0])) {
        cols = Object.keys(rows[0]);
      }
    }

    return { title, cols, rows };
  }, [tableData]);

  // Filter rows based on search term
  const filteredRows = useMemo(() => {
    if (!normalized || !normalized.rows) return [];
    if (!searchTerm.trim()) return normalized.rows;

    const term = searchTerm.toLowerCase();
    return normalized.rows.filter(row => {
      if (Array.isArray(row)) {
        return row.some(cell => String(cell ?? '').toLowerCase().includes(term));
      }
      if (typeof row === 'object' && row !== null) {
        return Object.values(row).some(cell => String(cell ?? '').toLowerCase().includes(term));
      }
      return false;
    });
  }, [normalized, searchTerm]);

  // Generate CSV text string
  const generateCSVString = () => {
    if (!normalized || normalized.rows.length === 0) return '';
    const headerLine = normalized.cols.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',');
    const rowLines = normalized.rows.map(row => {
      if (Array.isArray(row)) {
        return row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',');
      }
      if (typeof row === 'object' && row !== null) {
        return normalized.cols.map(col => `"${String(row[col] ?? '').replace(/"/g, '""')}"`).join(',');
      }
      return '';
    });
    return [headerLine, ...rowLines].join('\n');
  };

  // Copy table contents as CSV to clipboard
  const handleCopyCSV = () => {
    const csvContent = generateCSVString();
    if (!csvContent) return;
    navigator.clipboard.writeText(csvContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Trigger browser download for CSV file
  const handleDownloadCSV = () => {
    const csvContent = generateCSVString();
    if (!csvContent) return;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const fileName = (normalized.title || 'query_results').toLowerCase().replace(/[^a-z0-9]/g, '_') + '.csv';
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Trigger browser download for Excel file
  const handleDownloadExcel = () => {
    if (!normalized || normalized.rows.length === 0) return;

    let tableHTML = `<table border="1"><thead><tr>`;
    normalized.cols.forEach(c => {
      tableHTML += `<th style="background:#0d1c31;color:#ffffff;font-weight:bold;padding:8px;">${String(c)}</th>`;
    });
    tableHTML += `</tr></thead><tbody>`;

    normalized.rows.forEach(row => {
      tableHTML += `<tr>`;
      if (Array.isArray(row)) {
        row.forEach(cell => {
          tableHTML += `<td style="padding:6px;">${String(cell ?? '')}</td>`;
        });
      } else if (typeof row === 'object' && row !== null) {
        normalized.cols.forEach(col => {
          tableHTML += `<td style="padding:6px;">${String(row[col] ?? '')}</td>`;
        });
      }
      tableHTML += `</tr>`;
    });
    tableHTML += `</tbody></table>`;

    const excelDoc = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
        <head>
          <meta http-equiv="content-type" content="application/vnd.ms-excel; charset=UTF-8">
          <!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Data</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->
        </head>
        <body>${tableHTML}</body>
      </html>`;

    const blob = new Blob([excelDoc], { type: 'application/vnd.ms-excel;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const fileName = (normalized.title || 'query_results').toLowerCase().replace(/[^a-z0-9]/g, '_') + '.xls';
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const hasRows = normalized && normalized.rows && normalized.rows.length > 0;
  const effectiveSummary = summary || tableData?.summary;

  return (
    <div className="cb-table-container">
      {/* Render Table ONLY if rows exist */}
      {hasRows && (
        <div className="cb-table-card">
          <div className="cb-table-header">
            {/* Line 1: Table Title */}
            <div className="cb-table-title-row">
              <Table size={15} className="cb-table-icon" />
              <span className="cb-table-title" title={normalized.title}>{normalized.title}</span>
            </div>

            {/* Line 2: Controls & Actions (Search Box, Copy Button, Records Badge) */}
            <div className="cb-table-controls-row">
              {normalized.rows.length > 3 && (
                <div className="cb-table-search-wrap">
                  <Search size={13} className="cb-table-search-icon" />
                  <input
                    type="text"
                    className="cb-table-search-input"
                    placeholder="Search..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              )}

              <button
                type="button"
                className="cb-table-copy-btn"
                onClick={handleCopyCSV}
                title="Copy table as CSV"
                aria-label="Copy data as CSV"
              >
                {copied ? <Check size={13} color="var(--status-online)" /> : <Copy size={13} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <span className="cb-table-badge">
                {normalized.rows.length} record{normalized.rows.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <div className="cb-table-scroll-wrapper">
            <table className="cb-data-table">
              <thead>
                <tr>
                  {normalized.cols.map((col, idx) => (
                    <th key={idx}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={normalized.cols.length || 1} className="cb-table-empty-td">
                      No matching rows found
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {Array.isArray(row)
                        ? row.map((cell, cIdx) => <td key={cIdx}>{String(cell ?? '')}</td>)
                        : normalized.cols.map((col, cIdx) => (
                            <td key={cIdx}>{String(row[col] ?? '')}</td>
                          ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Render Summary normally as plain text inline (without card box) */}
      {effectiveSummary && (
        <div className="cb-summary-text">
          {effectiveSummary}
        </div>
      )}

      {/* Download Action Buttons at the bottom of the response */}
      {hasRows && (
        <div className="cb-download-actions">
          <button
            type="button"
            className="cb-download-btn"
            onClick={handleDownloadCSV}
            title="Download table data as CSV"
          >
            <Download size={13} />
            <span>Download CSV</span>
          </button>

          <button
            type="button"
            className="cb-download-btn excel"
            onClick={handleDownloadExcel}
            title="Download table data as Excel spreadsheet"
          >
            <FileSpreadsheet size={13} />
            <span>Download Excel</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default ChatTable;
