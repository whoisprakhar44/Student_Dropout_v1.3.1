import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeft,
  MessageSquare,
  Search,
  Database,
  Layers,
  Table,
  Columns,
  Key,
  ShieldCheck,
  Users,
  MapPin,
  GraduationCap,
  Briefcase,
  HeartPulse,
  Sprout,
  Car,
  Landmark,
  Zap,
  TrendingUp,
  BarChart3,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Sparkles,
  HelpCircle,
  Loader2,
  X,
  Lock
} from 'lucide-react';
import { useChatbot } from '../hooks/useChatbot';
import { schemaService } from '../services/schemaService';

// Helper to assign relevant icons to schema groups
const getGroupIcon = (groupName) => {
  const name = (groupName || '').toUpperCase();
  if (name.includes('GEOGRAPHY')) return <MapPin size={20} className="cb-group-icon geo" />;
  if (name.includes('PERSON') || name.includes('HOUSEHOLD') || name.includes('IDENTITY')) return <Users size={20} className="cb-group-icon identity" />;
  if (name.includes('EDUCATION')) return <GraduationCap size={20} className="cb-group-icon edu" />;
  if (name.includes('EPFO') || name.includes('EMPLOYMENT') || name.includes('OCCUPATION')) return <Briefcase size={20} className="cb-group-icon work" />;
  if (name.includes('HEALTH')) return <HeartPulse size={20} className="cb-group-icon health" />;
  if (name.includes('AGRICULTURE')) return <Sprout size={20} className="cb-group-icon agri" />;
  if (name.includes('VEHICLES')) return <Car size={20} className="cb-group-icon vehicle" />;
  if (name.includes('LAND') || name.includes('PROPERTY')) return <Landmark size={20} className="cb-group-icon land" />;
  if (name.includes('UTILITY') || name.includes('UTILITIES')) return <Zap size={20} className="cb-group-icon zap" />;
  if (name.includes('P4') || name.includes('SCORING')) return <BarChart3 size={20} className="cb-group-icon score" />;
  if (name.includes('TREND')) return <TrendingUp size={20} className="cb-group-icon trend" />;
  if (name.includes('SECURITY') || name.includes('TRANSFER') || name.includes('WELFARE') || name.includes('SCHEMES')) return <ShieldCheck size={20} className="cb-group-icon shield" />;
  return <Database size={20} className="cb-group-icon default" />;
};

export const AboutSchemaView = () => {
  const {
    closeAboutView,
    selectedSchemaGroup,
    setSelectedSchemaGroup,
    sduiPrivileges,
    canShowAboutSection,
    userRole,
  } = useChatbot();

  // If user role does not have about_section permission
  if (!canShowAboutSection || sduiPrivileges?.showAboutSection === false) {
    return (
      <div className="cb-about-view">
        <div className="cb-about-header">
          <div className="cb-about-title-wrap">
            <Database size={22} className="cb-about-brand-icon" />
            <div>
              <h2 className="cb-about-title">Canonical Data Model Reference</h2>
              <p className="cb-about-subtitle">Role-Based Access Control</p>
            </div>
          </div>
          <button type="button" className="cb-about-close-btn" onClick={closeAboutView} aria-label="Close About">
            <X size={18} />
          </button>
        </div>
        <div className="cb-about-content" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '380px', textAlign: 'center', padding: '36px 20px' }}>
          <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'rgba(220, 38, 38, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px', color: '#dc2626' }}>
            <Lock size={28} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-color)' }}>Access Restricted</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '13.5px', maxWidth: '420px', lineHeight: 1.55, marginBottom: '22px' }}>
            Canonical schema metadata and data dictionary documentation is restricted for your role (<strong>{userRole || 'Citizen Viewer'}</strong>) under the AP Citizen 360 RBAC policy.
          </p>
          <button type="button" className="cb-button cb-button-primary" onClick={closeAboutView}>
            Return to Conversation
          </button>
        </div>
      </div>
    );
  }

  const [schemaData, setSchemaData] = useState(() => schemaService.getLocalCachedSchema());
  const [isLoading, setIsLoading] = useState(() => !schemaService.getLocalCachedSchema());
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTables, setExpandedTables] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);

  useEffect(() => {
    let isMounted = true;

    const loadSchema = async () => {
      try {
        const fresh = await schemaService.getOrUpdateCanonicalSchema();
        if (isMounted && fresh) {
          setSchemaData(fresh);
        }
      } catch (err) {
        console.warn('Error fetching canonical schema:', err);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadSchema();

    return () => {
      isMounted = false;
    };
  }, []);

  // Group tables by group name from the canonical schema
  const groupedData = useMemo(() => {
    if (!schemaData) return {};
    const groupsList = schemaData.groups || [];
    const tablesObj = schemaData.tables || {};

    const map = {};
    groupsList.forEach((group) => {
      map[group] = [];
    });

    Object.entries(tablesObj).forEach(([tableName, tableDetails]) => {
      const g = tableDetails.group || 'OTHER';
      if (!map[g]) {
        map[g] = [];
      }
      map[g].push({
        tableName,
        ...tableDetails
      });
    });

    return map;
  }, [schemaData]);

  // Filter groups and tables based on search query
  const filteredGroups = useMemo(() => {
    if (!schemaData) return [];
    const q = searchQuery.trim().toLowerCase();
    const groupsList = schemaData.groups || [];

    if (!q) {
      return groupsList.map((g) => ({
        groupName: g,
        tables: groupedData[g] || [],
        totalFields: (groupedData[g] || []).reduce((acc, t) => acc + (t.fieldCount || 0), 0)
      }));
    }

    return groupsList
      .map((g) => {
        const groupMatches = g.toLowerCase().includes(q);
        const matchingTables = (groupedData[g] || []).filter(
          (t) =>
            t.tableName.toLowerCase().includes(q) ||
            (t.description && t.description.toLowerCase().includes(q)) ||
            (t.fields && Object.keys(t.fields).some((f) => f.toLowerCase().includes(q)))
        );

        if (groupMatches || matchingTables.length > 0) {
          return {
            groupName: g,
            tables: groupMatches ? groupedData[g] || [] : matchingTables,
            totalFields: (groupedData[g] || []).reduce((acc, t) => acc + (t.fieldCount || 0), 0),
            matchingTablesCount: matchingTables.length
          };
        }
        return null;
      })
      .filter(Boolean);
  }, [schemaData, searchQuery, groupedData]);

  // Current tables list if a group is selected
  const activeGroupTables = useMemo(() => {
    if (!selectedSchemaGroup || !schemaData) return [];
    const tables = groupedData[selectedSchemaGroup] || [];
    const q = searchQuery.trim().toLowerCase();
    if (!q) return tables;

    return tables.filter(
      (t) =>
        t.tableName.toLowerCase().includes(q) ||
        (t.description && t.description.toLowerCase().includes(q)) ||
        (t.tableType && t.tableType.toLowerCase().includes(q)) ||
        (t.fields && Object.keys(t.fields).some((f) => f.toLowerCase().includes(q)))
    );
  }, [selectedSchemaGroup, schemaData, groupedData, searchQuery]);

  const toggleTableExpand = (tableName) => {
    setExpandedTables((prev) => ({
      ...prev,
      [tableName]: !prev[tableName]
    }));
  };

  const handleCopy = (text, key) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  return (
    <div className="cb-about-container" role="region" aria-label="AP Citizen 360 Data Model Reference">
      {/* Top Header Navigation Bar */}
      <div className="cb-about-header">
        <div className="cb-about-header-left">
          {selectedSchemaGroup ? (
            <button
              type="button"
              className="cb-about-back-btn"
              onClick={() => setSelectedSchemaGroup(null)}
              title="Back to All Groups"
              aria-label="Back to Groups"
            >
              <ArrowLeft size={16} />
              <span>Back to Groups</span>
            </button>
          ) : (
            <div className="cb-about-title-badge">
              <Database size={17} className="cb-about-db-icon" />
              <div>
                <h2 className="cb-about-title">{schemaData?.title || 'AP Citizen 360° Data Model'}</h2>
                <div className="cb-about-meta">
                  <span>DB: <strong>{schemaData?.databaseName || 'ap_citizen360'}</strong></span>
                  <span>•</span>
                  <span>{schemaData?.tableCount || 46} Tables</span>
                  <span>•</span>
                  <span>{schemaData?.totalFieldCount || 605} Fields</span>
                  <span>•</span>
                  <span className="cb-about-ver-tag">v{schemaData?.version || '3.0.0'}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="cb-about-header-actions">
          <button
            type="button"
            className="cb-about-chat-btn"
            onClick={closeAboutView}
            title="Back to Active Chat"
            aria-label="Back to Chat"
          >
            <MessageSquare size={15} />
            <span>Back to Chat</span>
          </button>
          <button
            type="button"
            className="cb-about-close-btn"
            onClick={closeAboutView}
            title="Close About View"
            aria-label="Close"
          >
            <X size={17} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="cb-about-content">
        {/* Loading State Spinner */}
        {isLoading && !schemaData ? (
          <div className="cb-about-empty-state" style={{ padding: '60px 24px' }}>
            <Loader2 size={32} className="cb-icon-spin" color="var(--primary-color)" />
            <p style={{ marginTop: '12px', fontSize: '14px', fontWeight: 600 }}>
              Loading Canonical Data Model & Reference Schema...
            </p>
          </div>
        ) : (
          <>
            {/* Search Bar */}
            <div className="cb-about-search-bar">
              <div className="cb-about-search-input-wrap">
                <Search size={16} className="cb-about-search-icon" />
                <input
                  type="text"
                  className="cb-about-search-input"
                  placeholder={
                    selectedSchemaGroup
                      ? `Search tables or columns in ${selectedSchemaGroup}...`
                      : 'Search groups, tables (e.g. dim_state, health, epfo), or column fields...'
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search canonical schema"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="cb-about-search-clear"
                    onClick={() => setSearchQuery('')}
                    title="Clear Search"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* View Mode: Selected Group Tables View */}
            {selectedSchemaGroup ? (
              <div className="cb-about-tables-view">
                {/* Group Banner */}
                <div className="cb-about-group-banner">
                  <div className="cb-about-group-banner-info">
                    <div className="cb-about-group-banner-icon">
                      {getGroupIcon(selectedSchemaGroup)}
                    </div>
                    <div>
                      <div className="cb-about-breadcrumbs">
                        <span
                          className="cb-breadcrumb-link"
                          onClick={() => setSelectedSchemaGroup(null)}
                        >
                          All Groups
                        </span>
                        <ChevronRight size={13} />
                        <span className="cb-breadcrumb-current">{selectedSchemaGroup}</span>
                      </div>
                      <h3 className="cb-about-group-heading">{selectedSchemaGroup}</h3>
                      <p className="cb-about-group-sub">
                        Showing {activeGroupTables.length} of {(groupedData[selectedSchemaGroup] || []).length} table
                        {(groupedData[selectedSchemaGroup] || []).length !== 1 ? 's' : ''} in this canonical domain
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="cb-about-return-groups-btn"
                    onClick={() => setSelectedSchemaGroup(null)}
                  >
                    <ArrowLeft size={14} />
                    <span>All Groups</span>
                  </button>
                </div>

                {/* Tables List */}
                {activeGroupTables.length === 0 ? (
                  <div className="cb-about-empty-state">
                    <HelpCircle size={32} />
                    <p>No tables match your search &quot;{searchQuery}&quot; in this group.</p>
                    <button
                      type="button"
                      className="cb-about-clear-filter-btn"
                      onClick={() => setSearchQuery('')}
                    >
                      Clear search filter
                    </button>
                  </div>
                ) : (
                  <div className="cb-about-tables-grid">
                    {activeGroupTables.map((tbl) => {
                      const isExpanded = Boolean(expandedTables[tbl.tableName]);
                      const fieldKeys = Object.keys(tbl.fields || {});

                      return (
                        <div key={tbl.tableName} className="cb-table-card">
                          {/* Table Card Header */}
                          <div className="cb-table-card-header">
                            <div className="cb-table-card-title-row">
                              <div className="cb-table-name-wrap">
                                <Table size={16} className="cb-table-icon" />
                                <span className="cb-table-name">{tbl.tableName}</span>
                                <button
                                  type="button"
                                  className="cb-table-copy-btn"
                                  onClick={() => handleCopy(tbl.tableName, `tbl_${tbl.tableName}`)}
                                  title="Copy table name"
                                >
                                  {copiedKey === `tbl_${tbl.tableName}` ? (
                                    <Check size={13} color="var(--status-online)" />
                                  ) : (
                                    <Copy size={13} />
                                  )}
                                </button>
                              </div>

                              <div className="cb-table-badges">
                                {tbl.tableType && (
                                  <span className={`cb-type-badge ${tbl.tableType}`}>
                                    {tbl.tableType}
                                  </span>
                                )}
                                {tbl.primaryKey && (
                                  <span className="cb-pk-badge" title={`Primary Key: ${tbl.primaryKey}`}>
                                    <Key size={11} />
                                    <span>{tbl.primaryKey}</span>
                                  </span>
                                )}
                                {tbl.fieldCount && (
                                  <span className="cb-fields-badge">
                                    <Columns size={11} />
                                    <span>{tbl.fieldCount} fields</span>
                                  </span>
                                )}
                              </div>
                            </div>

                            {/* Table Description */}
                            <p className="cb-table-description">{tbl.description}</p>
                          </div>

                          {/* Partition & Metadata Bar (if present) */}
                          {tbl.partitionedBy && tbl.partitionedBy.length > 0 && (
                            <div className="cb-table-partition-row">
                              <span className="cb-partition-label">Partitioned By:</span>
                              <span className="cb-partition-value">
                                {Array.isArray(tbl.partitionedBy)
                                  ? tbl.partitionedBy.join(', ')
                                  : String(tbl.partitionedBy)}
                              </span>
                            </div>
                          )}

                          {/* Expandable Fields Accordion */}
                          <div className="cb-table-card-footer">
                            <button
                              type="button"
                              className={`cb-table-expand-btn ${isExpanded ? 'expanded' : ''}`}
                              onClick={() => toggleTableExpand(tbl.tableName)}
                              aria-expanded={isExpanded}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Columns size={14} />
                                <span>
                                  {isExpanded ? 'Hide Fields & Schema' : `View ${fieldKeys.length} Fields & Schema`}
                                </span>
                              </div>
                              {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                            </button>
                          </div>

                          {/* Fields Table Collapsible Body */}
                          {isExpanded && (
                            <div className="cb-table-fields-wrap">
                              <table className="cb-fields-table">
                                <thead>
                                  <tr>
                                    <th style={{ width: '28%' }}>Column Name</th>
                                    <th style={{ width: '18%' }}>Data Type</th>
                                    <th style={{ width: '54%' }}>Description</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {fieldKeys.map((fieldName) => {
                                    const field = tbl.fields[fieldName] || {};
                                    const isPk = tbl.primaryKey === fieldName;
                                    const fieldType = (field.type || 'STRING').toUpperCase();

                                    return (
                                      <tr key={fieldName} className={isPk ? 'is-pk-row' : ''}>
                                        <td className="cb-field-name-cell">
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                            {isPk && <Key size={11} color="var(--accent-color)" title="Primary Key" />}
                                            <code>{fieldName}</code>
                                          </div>
                                        </td>
                                        <td>
                                          <span className={`cb-datatype-badge type-${fieldType.toLowerCase()}`}>
                                            {fieldType}
                                          </span>
                                        </td>
                                        <td className="cb-field-desc-cell">
                                          {field.description || '—'}
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              /* View Mode: All Groups Cards Grid View */
              <div className="cb-about-groups-view">
                {/* Overview / Introduction Hero Card */}
                <div className="cb-about-hero-card">
                  <div className="cb-about-hero-badge">
                    <Sparkles size={14} />
                    <span>Canonical Data Reference</span>
                  </div>
                  <h3 className="cb-about-hero-heading">Andhra Pradesh Citizen 360° Data Architecture</h3>
                  <p className="cb-about-hero-desc">
                    {schemaData?.description ||
                      'Structured Iceberg tables backing AP Citizen 360° analytics, master registries, entitlements, governance, and predictive models. Click any domain card below to explore its tables and schema.'}
                  </p>
                </div>

                {/* Groups Grid */}
                {filteredGroups.length === 0 ? (
                  <div className="cb-about-empty-state">
                    <HelpCircle size={32} />
                    <p>No groups or tables match &quot;{searchQuery}&quot;.</p>
                    <button
                      type="button"
                      className="cb-about-clear-filter-btn"
                      onClick={() => setSearchQuery('')}
                    >
                      Clear search filter
                    </button>
                  </div>
                ) : (
                  <div className="cb-groups-grid">
                    {filteredGroups.map((grp) => {
                      const tableCount = grp.tables.length;
                      const previewTables = grp.tables.slice(0, 4);

                      return (
                        <div
                          key={grp.groupName}
                          className="cb-group-card"
                          onClick={() => {
                            setSelectedSchemaGroup(grp.groupName);
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                          }}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              setSelectedSchemaGroup(grp.groupName);
                            }
                          }}
                          aria-label={`Explore domain ${grp.groupName}`}
                        >
                          <div className="cb-group-card-header">
                            <div className="cb-group-card-icon-wrap">
                              {getGroupIcon(grp.groupName)}
                            </div>
                            <span className="cb-group-card-count">
                              {tableCount} table{tableCount !== 1 ? 's' : ''}
                            </span>
                          </div>

                          <h4 className="cb-group-card-title">{grp.groupName}</h4>

                          <div className="cb-group-card-meta">
                            <span>{grp.totalFields} total fields</span>
                            {grp.matchingTablesCount && (
                              <span className="cb-group-match-tag">
                                {grp.matchingTablesCount} matching table{grp.matchingTablesCount !== 1 ? 's' : ''}
                              </span>
                            )}
                          </div>

                          {/* Table preview tags */}
                          <div className="cb-group-table-tags">
                            {previewTables.map((t) => (
                              <span key={t.tableName} className="cb-table-pill">
                                {t.tableName}
                              </span>
                            ))}
                            {tableCount > 4 && (
                              <span className="cb-table-pill more">+{tableCount - 4} more</span>
                            )}
                          </div>

                          <div className="cb-group-card-action">
                            <span>Explore Tables</span>
                            <ChevronRight size={15} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AboutSchemaView;
