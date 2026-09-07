const isNumeric = (value) => {
    return (
        value !== null &&
        value !== undefined &&
        value !== '' &&
        !isNaN(Number(value))
    );
};

const isDateLike = (value) => {
    if (!value) return false;

    const s = String(value);

    return (
        !isNaN(Date.parse(s)) ||
        /^\d{4}$/.test(s) ||
        /^\d{4}-\d{2}$/.test(s) ||
        /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$/i.test(s)
    );
};

export const getSupportedCharts = (tableData) => {
    if (!tableData?.rows?.length) {
        return [];
    }

    let columns = [];

    if (Array.isArray(tableData.columns)) {
        columns = tableData.columns.map((c) =>
            typeof c === 'object'
                ? c.key
                : c
        );
    }

    if (!columns.length) {
        columns = Object.keys(tableData.rows[0]);
    }

    const supported = [];

    /**
     * BAR CHART
     * Category + Numeric
     */
    if (columns.length === 2) {
        const [xKey, yKey] = columns;

        const numericValues =
            tableData.rows.filter((row) =>
                isNumeric(row[yKey])
            );

        const allNumeric =
            numericValues.length ===
            tableData.rows.length;

        if (allNumeric) {
            supported.push('bar');
        }

        /**
         * LINE CHART
         * Sequential/time-like + numeric
         */
        const allSequential =
            tableData.rows.every((row) =>
                isDateLike(row[xKey])
            );

        if (allSequential && allNumeric) {
            supported.push('line');
        }

        /**
         * PIE CHART
         * Category + numeric
         * <= 6 slices
         * positive values
         */
        const validPie =
            allNumeric &&
            tableData.rows.length >= 2 &&
            tableData.rows.length <= 6 &&
            tableData.rows.every(
                (row) => Number(row[yKey]) >= 0
            );

        if (validPie) {
            supported.push('pie');
        }
    }

    /**
     * MULTI-SERIES BAR
     *
     * Region | Sales | Profit
     */
    if (columns.length > 2) {
        const numberColumns =
            columns.slice(1).filter((col) =>
                tableData.rows.every((row) =>
                    isNumeric(row[col])
                )
            );

        if (numberColumns.length > 0) {
            supported.push('grouped-bar');
        }
    }

    return supported;
};
