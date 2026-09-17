<template>
  <div class="login-page">
    <!-- 左：品牌区 -->
    <section class="login-brand">
      <div class="brand-inner">
        <div class="brand-logo">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M15 10L20 7V17L15 14M4 6H13C14.1046 6 15 6.89543 15 8V16C15 17.1046 14.1046 18 13 18H4C2.89543 18 2 17.1046 2 16V8C2 6.89543 2.89543 6 4 6Z" stroke="url(#login-brand-grad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><defs><linearGradient id="login-brand-grad" x1="2" y1="6" x2="20" y2="18"><stop stop-color="#0e9f6e"/><stop offset="1" stop-color="#0b7a52"/></linearGradient></defs></svg>
          <span class="brand-logo-text">Video<span class="gold-text">Mind</span></span>
        </div>
        <h1 class="brand-title">解码每一帧，<br />结晶你的知识</h1>
        <p class="brand-desc">每一段视频，都藏着未被看见的知识。VideoMind 用原生多模态 AI，把画面、语音与细节，解码成结构化笔记与可视化讲义。</p>
        <StoryJourney size="md" class="brand-journey" />
        <div class="brand-features">
          <div class="bf-item"><span class="bf-icon">✦</span> 原生音画帧同屏理解</div>
          <div class="bf-item"><span class="bf-icon">✦</span> 4 小时长视频智能切分</div>
          <div class="bf-item"><span class="bf-icon">✦</span> JSON / Markdown / HTML 三重结晶</div>
        </div>
      </div>
    </section>

    <!-- 右：表单 -->
    <section class="login-panel">
      <div class="login-card-wrap">
        <div class="panel-heading">
          <h2>欢迎使用</h2>
          <p class="sub">{{ tabLabel }}</p>
        </div>
        <n-card class="login-card" :bordered="false">
          <n-tabs v-model:value="tab" type="line" justify-content="center" animated>
            <n-tab-pane name="password" tab="密码登录" />
            <n-tab-pane name="code" tab="验证码登录" />
            <n-tab-pane name="register" tab="注册账号" />
            <n-tab-pane name="reset" tab="找回密码" />
          </n-tabs>
          <n-form :model="form" @submit.prevent="handleSubmit" class="login-form">
            <n-form-item label="电子邮箱" path="email"><n-input v-model:value="form.email" :input-props="{ name:'email', autocomplete:'email', inputmode:'email' }" placeholder="name@company.com" size="large" @keydown.enter.prevent="handleSubmit" /></n-form-item>
            <n-form-item v-if="tab==='password'||tab==='register'" :label="tab==='register'?'设置密码':'密码'" path="password"><n-input v-model:value="form.password" :input-props="{ name:'password', autocomplete:tab==='password'?'current-password':'new-password' }" type="password" show-password-on="click" placeholder="至少 8 位字符" size="large" @keydown.enter.prevent="handleSubmit" /></n-form-item>
            <n-form-item v-if="tab==='reset'" label="新密码" path="password"><n-input v-model:value="form.password" :input-props="{ name:'new-password', autocomplete:'new-password' }" type="password" show-password-on="click" placeholder="至少 8 位字符" size="large" @keydown.enter.prevent="handleSubmit" /></n-form-item>
            <n-form-item v-if="tab==='code'||tab==='register'||tab==='reset'" :label="tab==='reset'?'重置验证码':'邮箱验证码'" path="code">
              <n-input-group>
                <n-input v-model:value="form.code" :input-props="{ name:'code', autocomplete:'one-time-code', inputmode:'numeric' }" placeholder="6 位验证码" size="large" @keydown.enter.prevent="handleSubmit" />
                <n-button type="primary" secondary size="large" :disabled="codeCountdown>0||!form.email" :loading="sendingCode" @click="handleSendCode" style="width:130px">{{ codeCountdown>0?`${codeCountdown}s`:'获取验证码' }}</n-button>
              </n-input-group>
            </n-form-item>
            <n-button type="primary" block size="large" class="submit-btn" attr-type="submit" :loading="submitting" :disabled="submitDisabled">{{ submitLabel }}</n-button>
          </n-form>
          <div v-if="hint" class="hint-msg">{{ hint }}</div>
          <div class="guest-entry">
            <div class="guest-note">游客模式可体验工作台，但无法保存个人历史与管理 API Key。</div>
            <n-button tertiary size="medium" type="warning" @click="handleGuest">以游客身份直接访问工作台</n-button>
          </div>
          <div class="switch-line" v-if="tab==='password'||tab==='code'"><n-button text size="small" @click="tab='register'">首次使用？注册账号</n-button><n-button text size="small" @click="tab='reset'">忘记密码？</n-button></div>
          <div class="switch-line" v-else><n-button text size="small" @click="tab='password'">返回登录</n-button></div>
        </n-card>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from 'vue'
import { api } from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import StoryJourney from '@/components/StoryJourney.vue'

const authStore = useAuthStore(); const router = useRouter(); const message = useMessage()
const tab = ref<'password'|'code'|'register'|'reset'>('password')
const sendingCode = ref(false); const submitting = ref(false); const codeCountdown = ref(0); const hint = ref('')
let timer: number | null = null
const form = reactive({ email:'', password:'', code:'' })
const handleGuest = () => router.push('/workbench')

const startCountdown = () => { if(timer) clearInterval(timer); codeCountdown.value=60; timer=window.setInterval(()=>{codeCountdown.value--;if(codeCountdown.value<=0&&timer){clearInterval(timer);timer=null}},1000) }
onUnmounted(()=>{if(timer)clearInterval(timer)})

const tabLabel = computed(()=>({password:'已注册用户 · 邮箱 + 密码登录',code:'已注册用户 · 邮箱验证码登录',register:'首次使用 · 邮箱 + 密码 + 验证码注册',reset:'通过邮箱验证码重置密码'}[tab.value]))
const submitLabel = computed(()=>({password:'登录工作台',code:'验证码登录',register:'验证并注册',reset:'重置密码并登录'}[tab.value]))
const submitDisabled = computed(()=>{if(!form.email)return true;if(tab.value==='password')return!form.password;if(tab.value==='code')return!form.code;return!form.password||!form.code})
const getPurpose = ()=>tab.value==='register'?'register':tab.value==='reset'?'reset_password':'login'

const handleSendCode = async () => {
  if(!form.email||codeCountdown.value>0)return; sendingCode.value=true;hint.value=''
  try { const res=await api<{ok:boolean;cooldown:number;dev_code?:string}>('/api/v1/auth/request-code',{method:'POST',json:{email:form.email.trim(),purpose:getPurpose()}})
    startCountdown(); const pl=tab.value==='register'?'注册验证码':tab.value==='reset'?'重置密码验证码':'登录验证码'; let msg=`${pl}已发送到您的邮箱`; if(res.dev_code) msg+=`（测试模式 code=${res.dev_code}）`; hint.value=msg;message.success(msg)
  } catch(e:any){message.error(e.message||'发送失败');hint.value=e.message} finally{sendingCode.value=false}
}

const handleSubmit = async () => {
  submitting.value=true;hint.value=''
  try { let token:string
    if(tab.value==='password'){ const r=await api<{access_token:string}>('/api/v1/auth/login-password',{method:'POST',json:{email:form.email.trim(),password:form.password}});token=r.access_token }
    else if(tab.value==='code'){ const r=await api<{access_token:string}>('/api/v1/auth/verify',{method:'POST',json:{email:form.email.trim(),code:form.code.trim()}});token=r.access_token }
    else if(tab.value==='register'){ const r=await api<{access_token:string}>('/api/v1/auth/register',{method:'POST',json:{email:form.email.trim(),password:form.password,code:form.code.trim()}});token=r.access_token }
    else { await api('/api/v1/auth/reset-password',{method:'POST',json:{email:form.email.trim(),code:form.code.trim(),new_password:form.password}}); const r=await api<{access_token:string}>('/api/v1/auth/login-password',{method:'POST',json:{email:form.email.trim(),password:form.password}});token=r.access_token }
    await authStore.login(token)
    const st=tab.value==='register'?'注册成功，已自动登录':tab.value==='code'?'验证码登录成功':tab.value==='reset'?'密码已重置，登录成功':'密码登录成功';message.success(st);router.push('/workbench')
  } catch(e:any){message.error(e.message||'操作失败');hint.value=e.message}finally{submitting.value=false}
}
</script>

<style scoped>
.login-page { display: flex; min-height: calc(100vh - 56px) }
.login-brand { flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; padding: 48px; background: linear-gradient(160deg, #e9f6f0 0%, #ddf1e8 55%, #f7f0e2 100%) }
.brand-inner { max-width: 460px; width: 100% }
.brand-logo { display: flex; align-items: center; gap: 10px; margin-bottom: 28px }
.brand-logo-text { font-size: 1.4rem; font-weight: 800; color: var(--text-main) }
.gold-text { color: var(--emerald-deep) }
.brand-title { font-size: 2.4rem; font-weight: 900; line-height: 1.25; color: var(--text-main); margin: 0 0 16px; letter-spacing: -0.01em }
.brand-desc { font-size: 0.95rem; line-height: 1.75; color: var(--text-muted); margin: 0 0 24px }
.brand-journey { max-width: 320px; margin: 0 0 24px }
.brand-features { display: flex; flex-direction: column; gap: 10px }
.bf-item { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; font-weight: 500; color: var(--text-main) }
.bf-icon { color: var(--emerald-primary); font-size: 0.85rem }

.login-panel { width: 480px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; padding: 40px 40px; background: var(--bg-base) }
.login-card-wrap { width: 100%; max-width: 420px }
.panel-heading { margin-bottom: 16px }
.panel-heading h2 { font-size: 1.5rem; font-weight: 800; color: var(--text-main); margin: 0 0 4px }
.panel-heading .sub { font-size: 0.88rem; color: var(--text-muted); margin: 0 }
.login-card { padding: 12px 8px 16px }
.login-form { margin-top: 12px }
.submit-btn { height: 46px; font-size: 1rem; margin-top: 8px; border-radius: 9px }
.hint-msg { margin-top: 14px; padding: 10px 14px; border-radius: 8px; background: var(--emerald-soft); border: 1px solid rgba(14,159,110,0.3); color: var(--emerald-deep); font-size: 0.85rem; text-align: center }
.guest-entry { margin-top: 16px; display: flex; flex-direction: column; align-items: center; gap: 8px }
.guest-note { font-size: 0.8rem; color: var(--text-dim); text-align: center; line-height: 1.5 }
.switch-line { margin-top: 14px; display: flex; justify-content: center; gap: 16px }

@media (max-width: 900px) {
  .login-brand { display: none }
  .login-panel { width: 100%; padding: 32px 20px }
}
</style>
