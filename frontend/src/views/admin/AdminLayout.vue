<template>
  <el-container class="admin-layout">
    <el-aside width="210px" class="aside">
      <div class="logo">校务知识中台</div>
      <el-menu router :default-active="$route.path" class="menu">
        <el-menu-item index="/admin/sources">采集源管理</el-menu-item>
        <el-menu-item index="/admin/tasks">采集任务</el-menu-item>
        <el-menu-item index="/admin/knowledge">知识库管理</el-menu-item>
        <el-menu-item index="/admin/stats">资产全景</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">校务知识中台 · 管理端</span>
        <el-link href="/" target="_blank" type="primary">打开问答端 →</el-link>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
// 管理端布局：左侧菜单 + 顶栏 + 内容区
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}
.aside {
  background: #001529;
}
.logo {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  padding: 18px 0;
}
.menu {
  border-right: none;
  background: transparent;
  --el-menu-text-color: #bfcbd9;
  --el-menu-hover-bg-color: #1f2d3d;
  --el-menu-active-color: #409eff;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.main {
  background: #f5f7fa;
}
</style>
