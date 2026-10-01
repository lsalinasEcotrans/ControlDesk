import { LoginForm } from "@/components/login-form"
import Image from "next/image"

function BrandLogo({
  className,
  textClassName,
}: {
  className?: string
  textClassName?: string
}) {
  return (
    <div className={className}>
      <div className="relative flex size-14 items-center justify-center">
        <Image
          src="/icon.png"
          alt=""
          width={512}
          height={512}
          priority
          className="size-full object-contain"
        />
      </div>
      <span
        className={`font-ecotrans text-3xl font-semibold ${textClassName ?? ""}`}
      >
        <span className="text-verde">Eco</span>
        <span className="text-negro">trans</span>
      </span>
    </div>
  )
}

export default function LoginPage() {
  return (
    <div className="flex min-h-dvh w-full">
      {/* Panel de marca (izquierda) */}
      <div className="relative hidden w-[45%] flex-col justify-between overflow-hidden bg-sidebar p-10 lg:flex">
        <Image
          src="/images/login-brand.png"
          alt=""
          fill
          priority
          sizes="(min-width: 1024px) 45vw, 100vw"
          className="object-cover"
        />
        <div className="absolute inset-0 bg-linear-to-t from-sidebar via-sidebar/70 to-sidebar/20" />

        <BrandLogo
          className="relative z-10 flex items-center gap-2.5"
          textClassName="text-sidebar-foreground"
        />

        <div className="relative z-10 max-w-md">
          <p className="text-2xl leading-snug font-medium text-pretty text-sidebar-foreground">
            Gestiona rutas, flota y equipos desde un solo panel.
          </p>
          <p className="mt-3 text-sm text-sidebar-foreground/60">
            Plataforma interna de Ecotrans para la administración de
            operaciones.
          </p>
        </div>

        {/* Footer opcional */}
        <p className="relative z-10 text-xs text-sidebar-foreground/40">
          © {new Date().getFullYear()} Ecotrans. Todos los derechos reservados.
        </p>
      </div>

      {/* Panel del formulario (derecha) */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Logo visible solo en móvil */}
          <BrandLogo
            className="mb-8 flex items-center justify-center gap-2.5 lg:hidden"
            textClassName="text-foreground"
          />

          <LoginForm />
        </div>
      </div>
    </div>
  )
}
