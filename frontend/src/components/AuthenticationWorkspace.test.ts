import {describe,expect,it} from 'vitest';
import {authenticationWorkspaceUrl} from './AuthenticationWorkspace';

describe('embedded authentication workspace',()=>{
  it('uses the local proxy and follows the app theme',()=>{
    expect(authenticationWorkspaceUrl('',true)).toBe('/d2?embedded=1&theme=light');
    expect(authenticationWorkspaceUrl('',false)).toBe('/d2?embedded=1&theme=dark');
  });

  it('normalizes a configured API base URL',()=>{
    expect(authenticationWorkspaceUrl('http://127.0.0.1:8000/',true)).toBe('http://127.0.0.1:8000/d2?embedded=1&theme=light');
  });

  it('passes Hindi to the embedded workspace',()=>{
    expect(authenticationWorkspaceUrl('',true,'hi')).toBe('/d2?embedded=1&theme=light&lang=hi');
  });
});
