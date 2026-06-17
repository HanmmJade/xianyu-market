<script setup>
import { RouterView } from 'vue-router'
import Silk from './components/vue-bits/Silk.vue'
import TargetCursor from './components/vue-bits/TargetCursor.vue'
</script>

<template>
  <div style="position: relative; min-height: 100vh; background: #000;">
    <!-- Silk 丝绸背景 -->
    <Silk
      :speed="6"
      :scale="1"
      color="#ffffff"
      :noise-intensity="1.5"
      :rotation="0"
      style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; opacity: 0.9;"
    />

    <!-- TargetCursor 自定义光标 -->
    <TargetCursor
      :spin-duration="2"
      :hide-default-cursor="true"
      :parallax-on="true"
    />

    <!-- 页面内容 -->
    <div style="position: relative; z-index: 10;">
      <RouterView />
    </div>
  </div>
</template>
