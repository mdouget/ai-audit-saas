const modules = [
  ['Governance', 'Policy, accountability and AI oversight'],
  ['Security', 'Identity, model safety and misuse prevention'],
  ['Privacy', 'Data processing, retention and exposure'],
  ['Vendor oversight', 'External AI tool risk and due diligence'],
  ['Operational readiness', 'Incident response, monitoring and training'],
];
export default function Home() {
  return <main style={{maxWidth:1060,margin:'auto',padding:'48px 24px'}}>
    <header style={{display:'flex',justifyContent:'space-between',alignItems:'center',borderBottom:'1px solid #d9e1ed',paddingBottom:20}}>
      <div><strong style={{fontSize:26}}>AI Assurance</strong><div style={{color:'#5b6e86'}}>AI Governance · Security · Risk · Readiness</div></div>
      <span style={{padding:'8px 14px',background:'#e8effb',borderRadius:20}}>MVP preview</span>
    </header>
    <section style={{margin:'60px 0 32px'}}>
      <p style={{fontSize:14,textTransform:'uppercase',letterSpacing:2,color:'#3867af'}}>AI audit workspace</p>
      <h1 style={{fontSize:48,maxWidth:720,lineHeight:1.1}}>Understand your organization's AI risk.</h1>
      <p style={{fontSize:19,maxWidth:760,lineHeight:1.6,color:'#52657e'}}>Assess AI practices, track governance maturity, document findings, and build evidence-backed remediation plans.</p>
    </section>
    <section style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:16}}>
      {modules.map(([name,description])=><article key={name} style={{background:'white',padding:24,border:'1px solid #e0e5ed',borderRadius:14}}>
        <h2 style={{fontSize:18}}>{name}</h2><p style={{color:'#617189',lineHeight:1.5}}>{description}</p>
      </article>)}
    </section>
    <p style={{marginTop:32}}><a href="/dashboard">Open assessment workspace</a></p>
  </main>;
}
