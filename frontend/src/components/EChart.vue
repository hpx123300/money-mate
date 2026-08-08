<!-- ECharts 封装：传入 option 自动渲染，窗口变化自动重绘 -->

<script setup lang="ts">
import * as echarts from "echarts";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{ option: echarts.EChartsOption }>();

const el = ref<HTMLDivElement>();
let chart: echarts.ECharts | null = null;

function render() {
  if (!el.value) return;
  if (!chart) chart = echarts.init(el.value);
  chart.setOption(props.option);
}

function onResize() {
  chart?.resize();
}

onMounted(() => {
  render();
  window.addEventListener("resize", onResize);
});

watch(() => props.option, render, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener("resize", onResize);
  chart?.dispose();
});
</script>

<template>
  <div ref="el" style="width: 100%; height: 340px"></div>
</template>

