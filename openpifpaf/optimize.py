import logging
import torch

LOG = logging.getLogger(__name__)


def cli(parser):
    group = parser.add_argument_group('optimizer')
    group.add_argument('--momentum', type=float, default=0.9,
                       help='SGD momentum, beta1 in Adam')
    group.add_argument('--beta2', type=float, default=0.999,
                       help='beta2 for Adam/AMSGrad')
    group.add_argument('--adam-eps', type=float, default=1e-6,
                       help='eps value for Adam/AMSGrad')
    group.add_argument('--no-nesterov', dest='nesterov', default=True, action='store_false',
                       help='do not use Nesterov momentum for SGD update')
    group.add_argument('--weight-decay', type=float, default=0.0,
                       help='SGD/Adam/AMSGrad weight decay')
    group.add_argument('--adam', action='store_true',
                       help='use Adam optimizer')
    group.add_argument('--amsgrad', action='store_true',
                       help='use Adam optimizer with AMSGrad option')

    group_s = parser.add_argument_group('learning rate scheduler')
    group_s.add_argument('--lr', type=float, default=1e-3,
                         help='learning rate')
    group_s.add_argument('--lr-decay', default=[], nargs='+', type=float,
                         help='epochs at which to decay the learning rate')
    group_s.add_argument('--lr-decay-factor', default=0.1, type=float,
                         help='learning rate decay factor')
    group_s.add_argument('--lr-decay-duration', default=1.0, type=float,
                         help='learning rate decay duration in epochs')
    group_s.add_argument('--lr-burn-in-start-epoch', default=0, type=float,
                         help='starting epoch for burn-in')
    group_s.add_argument('--lr-burn-in-epochs', default=2, type=float,
                         help='number of epochs at the beginning with lower learning rate')
    group_s.add_argument('--lr-burn-in-factor', default=0.001, type=float,
                         help='learning pre-factor during burn-in')


class LearningRateLambda(object):
    def __init__(self, burn_in_duration, decay_schedule, *,
                 decay_factor=0.1,
                 decay_duration=1.0,
                 burn_in_start=0,
                 burn_in_factor=0.01):
        self.burn_in_duration = burn_in_duration
        self.decay_schedule = decay_schedule
        self.decay_factor = decay_factor
        self.decay_duration = decay_duration
        self.burn_in_start = burn_in_start
        self.burn_in_factor = burn_in_factor

    def __call__(self, step_i):
        lambda_ = 1.0

        if step_i <= self.burn_in_start:
            lambda_ *= self.burn_in_factor

        if self.burn_in_start < step_i < self.burn_in_start + self.burn_in_duration:
            lambda_ *= self.burn_in_factor**(
                1.0 - (step_i - self.burn_in_start) / self.burn_in_duration
            )

        for d in self.decay_schedule:
            if step_i >= d + self.decay_duration:
                lambda_ *= self.decay_factor
            elif step_i > d:
                lambda_ *= self.decay_factor**(
                    (step_i - d) / self.decay_duration
                )

        return lambda_


def factory_optimizer(args, parameters):
    if args.amsgrad:
        args.adam = True

    if args.adam:
        LOG.info('Adam optimizer')
        optimizer = torch.optim.Adam(
            (p for p in parameters if p.requires_grad),
            lr=args.lr, betas=(args.momentum, args.beta2),
            weight_decay=args.weight_decay, eps=args.adam_eps, amsgrad=args.amsgrad)
    else:
        LOG.info('SGD optimizer')
        optimizer = torch.optim.SGD(
            (p for p in parameters if p.requires_grad),
            lr=args.lr, momentum=args.momentum, weight_decay=args.weight_decay,
            nesterov=args.nesterov)

    return optimizer


def factory_lrscheduler(args, optimizer, training_batches_per_epoch):
    return torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        [LearningRateLambda(args.lr_burn_in_epochs * training_batches_per_epoch,
                            [s * training_batches_per_epoch for s in args.lr_decay],
                            decay_factor=args.lr_decay_factor,
                            decay_duration=args.lr_decay_duration * training_batches_per_epoch,
                            burn_in_start=args.lr_burn_in_start_epoch * training_batches_per_epoch,
                            burn_in_factor=args.lr_burn_in_factor)],
    )
