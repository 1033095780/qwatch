// utils/integration.ts — v0.2 接入示例（POST /report，instrument 必填），供创建策略/令牌弹窗复用。
export function reportCurl(token: string, instrument = 'rb'): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8080';
  return [
    'curl -X POST ' + origin + '/api/v1/report \\',
    '  -H "Authorization: Bearer ' + token + '" \\',
    '  -H "Content-Type: application/json" \\',
    '  -d \'{"instrument":"' + instrument + '","loop":1,"msg":"heartbeat"}\'',
  ].join('\n');
}
