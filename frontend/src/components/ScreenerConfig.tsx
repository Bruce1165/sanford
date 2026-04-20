import React, { useState, useEffect } from 'react';
import { Button, Input, InputNumber, Table, Typography, Tag, Alert, message, Spin } from 'antd';
import { SaveOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import { apiRequest } from '../api/index';

const { Text } = Typography;

interface Parameter {
  value: any;
  display_name: string;
  description: string;
  group: string;
  type: 'int' | 'float' | 'bool' | 'string';
  min?: number;
  max?: number;
  step?: number;
  default?: any;
}

interface ScreenerConfig {
  display_name: string;
  description: string;
  category: string;
  metadata: {
    version: string;
    created: string;
  };
  parameters: Record<string, Parameter>;
}

interface ScreenerConfigProps {
  screenerName: string;
  onClose?: () => void;
}

interface ParameterRow {
  key: string;
  name: string;
  displayName: string;
  description: string;
  group: string;
  type: string;
  value: any;
  minValue?: number;
  maxValue?: number;
  step?: number;
  defaultValue: any;
  isModified: boolean;
}

export const ScreenerConfig: React.FC<ScreenerConfigProps> = ({ screenerName, onClose: _onClose }) => {
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<ScreenerConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [originalValues, setOriginalValues] = useState<Record<string, any>>({});
  const [parameters, setParameters] = useState<ParameterRow[]>([]);

  // Helper to get clean name (remove '_screener' suffix)
  // Keep screenerName as-is for API calls (no suffix removal needed)

  useEffect(() => {
    loadConfig();
  }, [screenerName]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const configData = await apiRequest<ScreenerConfig>(
        `/screeners/${screenerName}/config`
      );

      if (!configData || !configData.parameters) {
        console.error('Invalid config structure:', configData);
        message.error('配置数据格式错误');
        setLoading(false);
        return;
      }

      console.log('[FRONTEND DEBUG] Setting config to state:', configData);
      setConfig(configData);

      // Convert parameters to table rows
      const rows: ParameterRow[] = Object.entries(configData.parameters || {}).map(([key, param]: [string, any]) => ({
        key: key,
        name: key,
        displayName: param.display_name,
        description: param.description,
        group: param.group || '其他',
        type: param.type,
        value: param.value,
        minValue: param.min,
        maxValue: param.max,
        step: param.step || 1,
        defaultValue: param.default,
        isModified: param.value !== param.default
      }));

      setParameters(rows);

      // Initialize original values
      const formValues: Record<string, any> = {};
      Object.entries(configData.parameters || {}).forEach(([key, param]: [string, any]) => {
        formValues[key] = param.value;
      });
      setOriginalValues(formValues);
      setUnsavedChanges(false);
    } catch (error) {
      console.error('Error in loadConfig:', error);
      message.error('加载配置失败: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleValueChange = (key: string, newValue: any) => {
    const updated = parameters.map(p => {
      if (p.key === key) {
        return { ...p, value: newValue, isModified: newValue !== p.defaultValue };
      }
      return p;
    });
    setParameters(updated);

    // Check for unsaved changes
    const hasChanges = updated.some(p => p.value !== originalValues[p.key]);
    setUnsavedChanges(hasChanges);
  };

  const handleSave = async () => {
    if (!config) return;

    console.log('[DEBUG] handleSave 开始');
    console.log('[DEBUG] screenerName:', screenerName);
    console.log('[DEBUG] 当前 parameters:', parameters);

    setSaving(true);
    try {
      // Build updated parameters
      const updatedParameters: Record<string, Parameter> = {};
      parameters.forEach(row => {
        updatedParameters[row.name] = {
          ...config.parameters[row.name],
          value: row.value
        };
      });

      console.log('[DEBUG] updatedParameters:', JSON.stringify(updatedParameters, null, 2));

      const requestBody = {
        parameters: updatedParameters,
        change_summary: '配置更新'
      };
      console.log('[DEBUG] 发送请求体:', JSON.stringify(requestBody, null, 2));
      console.log('[DEBUG] 请求 URL:', `/screeners/${screenerName}/config`);

      const data = await apiRequest<{ status: string; config: ScreenerConfig }>(
        `/screeners/${screenerName}/config`,
        {
          method: 'PUT',
          body: JSON.stringify(requestBody)
        }
      );

      console.log('[DEBUG] 响应数据:', data);
      message.success(`配置已保存！版本: ${data.config?.metadata?.version || 'v1.0'}`);

      // Update original values after successful save
      const newValues: Record<string, any> = {};
      Object.keys(updatedParameters).forEach(key => {
        newValues[key] = updatedParameters[key].value;
      });
      setOriginalValues(newValues);
      setUnsavedChanges(false);

      loadConfig();
    } catch (error) {
      message.error('保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const resetParams = parameters.map(p => ({
      ...p,
      value: originalValues[p.name],
      isModified: originalValues[p.name] !== p.defaultValue
    }));
    setParameters(resetParams);
    setUnsavedChanges(false);
    message.info('已重置为当前保存的值');
  };

  const columns = [
    {
      title: '参数名称',
      dataIndex: 'displayName',
      key: 'displayName',
      width: 180,
      render: (text: string, record: ParameterRow) => (
        <div>
          <div style={{ color: '#111827', fontWeight: 500 }}>{text}</div>
          <div style={{ color: '#6b7280', fontSize: '12px' }}>{record.name}</div>
        </div>
      )
    },
    {
      title: '当前值',
      dataIndex: 'value',
      key: 'value',
      width: 150,
      render: (value: any, record: ParameterRow) => {
        const inputStyle = {
          width: '100%',
          padding: '4px 8px',
          border: '1px solid #d1d5db',
          borderRadius: '4px',
          fontSize: '14px',
          backgroundColor: '#ffffff',
          color: '#111827'
        };

        if (record.type === 'bool') {
          return (
            <select
              value={String(value)}
              onChange={(e) => handleValueChange(record.key, e.target.value === 'true')}
              style={inputStyle}
            >
              <option value="true">是</option>
              <option value="false">否</option>
            </select>
          );
        } else if (record.type === 'string') {
          return (
            <Input
              value={value}
              onChange={(e) => handleValueChange(record.key, e.target.value)}
              style={inputStyle}
            />
          );
        } else {
          return (
            <InputNumber
              value={value}
              onChange={(newValue) => handleValueChange(record.key, newValue)}
              min={record.minValue}
              max={record.maxValue}
              step={record.step}
              precision={record.type === 'float' ? 2 : 0}
              style={inputStyle}
            />
          );
        }
      }
    },
    {
      title: '默认值',
      dataIndex: 'defaultValue',
      key: 'defaultValue',
      width: 100,
      render: (value: any) => (
        <span style={{ color: '#6b7280' }}>{String(value)}</span>
      )
    },
    {
      title: '有效范围',
      key: 'range',
      width: 120,
      render: (_: any, record: ParameterRow) => (
        <span style={{ color: '#6b7280', fontSize: '13px' }}>
          {record.minValue !== undefined && record.maxValue !== undefined
            ? `${record.minValue} ~ ${record.maxValue}`
            : record.minValue !== undefined
            ? `≥${record.minValue}`
            : record.maxValue !== undefined
            ? `≤${record.maxValue}`
            : '-'
          }
        </span>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (type: string) => (
        <span style={{ color: '#6b7280', fontSize: '13px' }}>{type}</span>
      )
    },
    {
      title: '分组',
      dataIndex: 'group',
      key: 'group',
      width: 100,
      render: (group: string) => (
        <span style={{ color: '#6b7280', fontSize: '13px' }}>{group}</span>
      )
    },
    {
      title: '状态',
      key: 'status',
      width: 80,
      render: (_: any, record: ParameterRow) => {
        if (record.isModified) {
          return <span style={{ color: '#d97706', fontWeight: 500, fontSize: '13px' }}>已修改</span>;
        }
        return <span style={{ color: '#059669', fontSize: '13px' }}>默认</span>;
      }
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (description: string) => (
        <Text style={{ color: '#374151', fontSize: '13px' }}>{description}</Text>
      )
    }
  ];

  if (loading) {
    return (
      <div style={{ padding: '48px', textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: '16px' }}>
          <Text style={{ color: '#94a3b8', fontSize: '14px' }}>加载配置中...</Text>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div style={{ padding: '48px' }}>
        <Alert
          message="配置未找到"
          description="无法加载筛选器配置"
          type="error"
          showIcon
          style={{ background: '#fee2e2', border: '1px solid #ef4444' }}
        />
      </div>
    );
  }

  return (
    <div style={{ background: '#ffffff' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '2px solid #e5e7eb', background: '#f9fafb' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ color: '#111827', margin: 0, marginBottom: '8px' }}>
              {config.display_name}
            </h2>
            <Text style={{ fontSize: '13px', color: '#6b7280' }}>
              {screenerName} | 版本: {config.metadata?.version}
            </Text>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleReset}
              disabled={!unsavedChanges}
            >
              重置
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              disabled={!unsavedChanges}
              loading={saving}
              size="large"
              style={{ minWidth: '120px' }}
            >
              保存配置
            </Button>
          </div>
        </div>
      </div>

      {/* Warning for unsaved changes */}
      {unsavedChanges && (
        <div style={{ padding: '0 24px', marginTop: '16px' }}>
          <Alert
            message="您有未保存的变更"
            description="请点击保存按钮使更改生效"
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            closable
          />
        </div>
      )}

      {/* Parameters Table */}
      <div style={{ padding: '24px' }}>
        <div style={{ border: '1px solid #d1d5db', borderRadius: '4px', overflow: 'hidden' }}>
          <Table
            columns={columns}
            dataSource={parameters}
            pagination={false}
            size="small"
            scroll={{ x: 1200, y: 500 }}
            rowKey="key"
            bordered={true}
            style={{ background: '#ffffff' }}
          />
        </div>
      </div>

      {/* Description Card */}
      <div style={{ padding: '0 24px 24px' }}>
        <div style={{ border: '1px solid #e5e7eb', borderRadius: '4px', padding: '20px', background: '#f9fafb' }}>
          <h3 style={{ color: '#111827', marginBottom: '12px', fontSize: '16px' }}>筛选器说明</h3>
          <Text style={{ color: '#374151', fontSize: '14px', lineHeight: '1.6' }}>
            {config.description || '暂无描述'}
          </Text>
          <div style={{ marginTop: '12px' }}>
            <Tag color="blue">{config.category}</Tag>
          </div>
        </div>
      </div>
    </div>
  );
};
