import React from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Button } from 'antd';
import { VideoCameraOutlined, AppstoreOutlined, FileTextOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const quickActions = [
    {
      title: 'Генерация видео',
      description: 'Создание Reels с наложением текста и музыки',
      icon: <VideoCameraOutlined style={{ fontSize: 24, color: '#1890ff' }} />,
      onClick: () => navigate('/video'),
      color: '#1890ff'
    },
    {
      title: 'Генерация каруселей',
      description: 'Создание каруселей из изображений с текстом',
      icon: <AppstoreOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
      onClick: () => navigate('/carousel'),
      color: '#52c41a'
    },
    {
      title: 'Управление шаблонами',
      description: 'Создание и редактирование шаблонов',
      icon: <FileTextOutlined style={{ fontSize: 24, color: '#fa8c16' }} />,
      onClick: () => navigate('/templates'),
      color: '#fa8c16'
    },
    {
      title: 'Профиль',
      description: 'Настройки аккаунта и лимиты',
      icon: <UserOutlined style={{ fontSize: 24, color: '#722ed1' }} />,
      onClick: () => navigate('/profile'),
      color: '#722ed1'
    }
  ];

  return (
    <div>
      <Title level={2}>Панель управления</Title>
      <p>Добро пожаловать, {user?.full_name || user?.username}!</p>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Дневной лимит видео"
              value={user?.daily_video_limit || 0}
              suffix="роликов"
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Дневной лимит каруселей"
              value={user?.daily_carousel_limit || 0}
              suffix="каруселей"
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Подключенные соцсети"
              value={[user?.instagram_connected, user?.tiktok_connected].filter(Boolean).length}
              suffix="сетей"
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Язык интерфейса"
              value={user?.language === 'ru' ? 'Русский' : 'English'}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Title level={3}>Быстрые действия</Title>
      <Row gutter={[16, 16]}>
        {quickActions.map((action, index) => (
          <Col xs={24} sm={12} md={6} key={index}>
            <Card
              hoverable
              style={{ height: '100%' }}
              onClick={action.onClick}
            >
              <Space direction="vertical" size="middle" style={{ width: '100%', textAlign: 'center' }}>
                {action.icon}
                <div>
                  <Title level={4} style={{ margin: 0, color: action.color }}>
                    {action.title}
                  </Title>
                  <p style={{ margin: 0, color: '#666' }}>
                    {action.description}
                  </p>
                </div>
                <Button type="primary" style={{ backgroundColor: action.color, borderColor: action.color }}>
                  Перейти
                </Button>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Card style={{ marginTop: 24 }}>
        <Title level={3}>Последние активности</Title>
        <p>Здесь будут отображаться ваши последние генерации и активности.</p>
      </Card>
    </div>
  );
};

export default Dashboard;































