export default function Home() {
  return (
    <main style={{
      display: 'flex',
      minHeight: '100vh',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '6rem 1.5rem'
    }}>
      <div style={{
        maxWidth: '1200px',
        width: '100%',
        textAlign: 'center'
      }}>
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: 'bold',
          marginBottom: '2rem'
        }}>
          My Library
        </h1>
        <p style={{
          fontSize: '1.25rem',
          marginBottom: '1rem'
        }}>
          マンガ管理アプリケーション
        </p>
        <div style={{
          backgroundColor: '#f3f4f6',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          marginTop: '2rem'
        }}>
          <p style={{
            fontSize: '0.875rem',
            color: '#6b7280'
          }}>
            所持しているマンガを管理・検索できます
          </p>
        </div>
      </div>
    </main>
  )
}
