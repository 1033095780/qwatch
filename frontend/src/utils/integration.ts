// utils/integration.ts — 策略接入示例（心跳 curl），供创建策略/令牌弹窗复用。
export function heartbeatCurl(token: string, runnerName: string): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8080';
  return [
    'curl -X POST ' + origin + '/api/v1/heartbeat \\',
    '  -H "Authorization: Bearer ' + token + '" \\',
    '  -H "Content-Type: application/json" \\',
    '  -d \'{"runner_id":"' + runnerName + '","seq":1,"state":"running","loop_count":1}\'',
  ].join('\n');
}
