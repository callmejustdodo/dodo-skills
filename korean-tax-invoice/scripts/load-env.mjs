/**
 * 스킬 폴더의 .env 를 읽는다. 각 스크립트가 맨 먼저 import 한다.
 *
 * 셸에 이미 있는 값이 이긴다 — .env 에 빈 키가 있어도 export 한 키를
 * 덮어쓰지 않는다. cwd 가 아니라 이 파일 위치 기준으로 찾으므로 어느
 * 디렉터리에서 돌려도 같은 .env 를 쓴다. 파일이 없으면 아무것도 하지 않는다.
 */

import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const envPath = join(dirname(fileURLToPath(import.meta.url)), '..', '.env')

if (existsSync(envPath)) {
  if (typeof process.loadEnvFile === 'function') {
    process.loadEnvFile(envPath)
  } else {
    // process.loadEnvFile 은 Node 20.12 / 21.7 부터 있다.
    console.error(`.env 를 읽으려면 Node 20.12 이상이 필요합니다 (현재 ${process.version}).`)
    console.error('키를 셸에서 export 하세요.\n')
  }
}
