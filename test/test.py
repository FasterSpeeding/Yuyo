import alluka
import yuyo.modals

class Modal(yuyo.modals.Modal):
    async def callback(self, ctx: yuyo.modals.ModalContext) -> None:
        raise NotADirectoryError()


reveal_type(Modal.callback)
reveal_type(Modal().callback)


@yuyo.modals.as_modal_template
async def callback(ctx: yuyo.modals.ModalContext, user: alluka.Injected[int]) -> None:
    ...


reveal_type(callback.callback)
reveal_type(callback().callback)


async def test_callback(ctx: yuyo.modals.ModalContext, user: int) -> None:
    await callback.callback(callback(), ctx, user)
    await callback().callback(ctx, user)


@yuyo.modals.as_modal
async def modal(ctx: yuyo.modals.ModalContext, bar: alluka.Injected[int]) -> None:
    ...


reveal_type(modal.callback)


